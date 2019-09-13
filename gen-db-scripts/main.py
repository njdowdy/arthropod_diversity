#!/usr/bin/env python3

import configparser
import numpy as np
import os
import pandas as pd
import pickle as pkl
import sqlite3
from datetime import datetime
from datetime import date

ANSI_CURSOR_BEGINNING_OF_LINE = u"\u001b[1000D"
ANSI_CURSOR_CLEAR_LINE = u"\u001b[0K"

sql_config_file = os.path.join(os.environ["HOME"], ".my.cnf")
sqlite_create_file = os.path.join(os.path.dirname(__file__), "create-db.sql")

meta_dir = os.path.join(os.path.dirname(__file__), "meta")
omoccurrences_countries_file = os.path.join(meta_dir, "omoccurrences-countries.pkl")
omoccurrences_states_file = os.path.join(meta_dir, "omoccurrences-states.pkl")
table_names_file = os.path.join(meta_dir, "table-names.pkl")
taxa_fields_file = os.path.join(meta_dir, "taxa-fields.pkl")

omoccurrences_longitude_range = [-178.2, -49.0]
omoccurrences_latitude_range = [6.6, 83.3]

cache_dir = ".cache"
omoccurrences_min_cache_file = os.path.join(cache_dir, "occid.pkl.gz")
omoccurrences_cache_file = os.path.join(cache_dir, "tbl_omoccurrences.pkl.gz")
omcollections_cache_file = os.path.join(cache_dir, "tbl_omcollections.pkl.gz")
taxa_cache_file = os.path.join(cache_dir, "tbl_taxa.pkl.gz")
taxaenumtree_cache_file = os.path.join(cache_dir, "tbl_taxaenumtree.pkl.gz")
taxonunits_cache_file = os.path.join(cache_dir, "tbl_taxonunits.pkl.gz")
institutions_cache_file = os.path.join(cache_dir, "tbl_institutions.pkl.gz")

sql_fmt_occid = "select occid, collid, tidinterpreted from omoccurrences "
sql_fmt_occid += "where (decimalLatitude between {} and {} and decimalLongitude between {} and {}) "
sql_fmt_occid += "or lower(country) in ({}) "
sql_fmt_occid += "or lower(stateProvince) in ({});"


def sqlite_create_db(sqlite_create_script, sqlite_outfile):
    with open(sqlite_create_script) as f:
        sqlite_create = f.read().strip()
    with sqlite3.connect(sqlite_outfile) as sqlite_conn:
        sqlite_conn.executescript(sqlite_create)


def meta_load_table_names(tbl_names_file):
    with open(tbl_names_file, "rb") as f:
        return pkl.load(f)


def meta_load_table_fields(table_names_array):
    table_fields = dict()
    for tn in table_names_array:
        with open(os.path.join(meta_dir, "{}-fields.pkl".format(tn)), "rb") as f:
            table_fields[tn] = pkl.load(f)
    return table_fields


def meta_load_omoccurrences_provinces(states_array_file):
    with open(states_array_file, "rb") as f:
        return pkl.load(f)


def meta_load_omoccurrences_countries(countries_array_file):
    with open(countries_array_file, "rb") as f:
        return pkl.load(f)


def meta_load_sql_uri_src(mysql_config_file, db_name):
    config_parser = configparser.ConfigParser()
    config_parser.read(mysql_config_file)
    sql_config = config_parser["client"]
    return "mysql://{}:{}@{}/{}".format(
        sql_config["user"],
        sql_config["password"],
        sql_config["host"],
        db_name
    )


def get_taxonunits_table(cache_file, sql_uri_src, fields, dtypes):
    if not os.path.exists(cache_file):
        print("Loading taxonunits from source database...")
        taxonunits_df = pd.read_sql(
            "select {} from taxonunits".format(", ".join(fields)),
            sql_uri_src
        ).astype(dtypes)
        taxonunits_df.to_pickle(cache_file)
    else:
        print("Loading taxonunits from cache...")
        taxonunits_df = pd.read_pickle(cache_file)
    print("Found {} rows in taxonunits".format(len(taxonunits_df.index)))
    print("Finished loading taxonunits\n")
    return taxonunits_df


def get_omoccurrences_min(cache_file, sql_uri_src, occ_countries, occ_provinces, occ_lat_range, occ_lon_range, dtypes):
    if not os.path.exists(cache_file):
        print("Loading occids from source database...")
        occid_df = pd.read_sql(
            sql_fmt_occid.format(
                occ_lat_range[0],
                occ_lat_range[1],
                occ_lon_range[0],
                occ_lon_range[1],
                "', '".join(["'{}'".format(c) for c in occ_countries]),
                "', '".join(["'{}'".format(s) for s in occ_provinces]),
            ),
            sql_uri_src
        ).astype(dtypes)
        occid_df.to_pickle(cache_file)
    else:
        print("Loading occids from cache...")
        occid_df = pd.read_pickle(cache_file)
    print("Found {} rows in omoccurrences".format(len(occid_df.index)))
    print("Finished loading occids\n")
    return occid_df


def get_omcollections_table(cache_file, sql_uri_src, fields, collids, dtypes):
    if not os.path.exists(cache_file):
        print("Loading omcollections from source database...")
        omcollections_df = pd.read_sql(
            "select {} from omcollections where collid in ({})".format(
                ", ".join(fields),
                ", ".join(collids)
            ),
            sql_uri_src
        ).astype(dtypes)
        omcollections_df.to_pickle(cache_file)
    else:
        print("Loading omcollections from cache...")
        omcollections_df = pd.read_pickle(cache_file)
    print("Found {} rows in omcollections".format(len(omcollections_df.index)))
    print("Finished loading omcollections\n")
    return omcollections_df


def get_institutions_table(cache_file, sql_uri_src, fields, iids, dtypes):
    if not os.path.exists(cache_file):
        print("Loading institutions from source database...")
        institutions_df = pd.read_sql(
            "select {} from institutions where iid in ({})".format(
                ", ".join(fields),
                ", ".join(iids)
            ),
            sql_uri_src
        ).astype(dtypes)
        institutions_df.to_pickle(cache_file)
    else:
        print("Loading institutions from cache...")
        institutions_df = pd.read_pickle(cache_file)
    print("Found {} rows in institutions".format(len(institutions_df.index)))
    print("Finished loading institutions\n")
    institutions_df = institutions_df.rename({"intialTimeStamp": "initialTimestamp"})
    return institutions_df


def get_taxaenumtree_table(cache_file, sql_uri_src, fields, initial_tids, dtypes):
    if not os.path.exists(cache_file):
        print("Loading taxaenumtree from source database...")
        taxa_recurse = [
            pd.read_sql(
                "select {} from taxaenumtree where tid in ({})".format(
                    ", ".join(fields),
                    ", ".join(initial_tids)
                ),
                sql_uri_src
            ).astype(dtypes)
        ]

        while True:
            tids = np.unique(
                taxa_recurse[-1]["parenttid"][~pd.isna(taxa_recurse[-1]["parenttid"])][taxa_recurse[-1]["parenttid"] != taxa_recurse[-1]["tid"]]
            ).astype(str).tolist()
            if len(tids) <= 0:
                break
            print("{}{}".format(ANSI_CURSOR_BEGINNING_OF_LINE, ANSI_CURSOR_CLEAR_LINE), end='', flush=True)
            print("Found {} new taxa".format(len(tids)), flush=True)
            current_taxa = pd.read_sql(
                "select {} from taxaenumtree where tid in ({})".format(
                    ", ".join(fields),
                    ", ".join(tids)
                ),
                sql_uri_src
            ).astype(dtypes)
            taxa_recurse.append(current_taxa)
        print()

        taxaenumtree_df = pd.DataFrame(data=taxa_recurse)
        taxaenumtree_df.to_pickle(cache_file)
    else:
        print("Loading taxaenumtree from cache...")
        taxaenumtree_df = pd.read_pickle(cache_file)
    print("Found {} rows in taxaenumtree".format(len(taxaenumtree_df.index)))
    print("Finished loading taxaenumtree\n")
    return taxaenumtree_df


def get_taxa_table(cache_file, sql_uri_src, fields, tids, dtypes):
    if not os.path.exists(cache_file):
        print("Loading taxa from source database...")
        taxa_df = pd.read_sql(
            "select {} from taxa where tid in ({})".format(
                ", ".join(fields),
                ", ".join(tids)
            ),
            sql_uri_src
        ).astype(dtypes)
        taxa_df.to_pickle(cache_file)
    else:
        print("Loading taxa from cache...")
        taxa_df = pd.read_pickle(cache_file)
    print("Found {} rows in taxa".format(len(taxa_df.index)))
    print("Finished loading taxa\n")
    return taxa_df

# TODO: All omoccurrence data, rename dateEntered & dateLastmodified to initialTimestamp and modifiedTimestamp


def main():
    # Load metadata
    today_timestamp = date.today().strftime("%Y-%m-%d")
    sqlite_outfile = os.path.join(os.path.dirname(__file__), "{}_symbscan.sqlite".format(today_timestamp))
    table_names = meta_load_table_names(table_names_file)
    table_fields = meta_load_table_fields(table_names)
    omoccurrences_provinces = meta_load_omoccurrences_provinces(omoccurrences_states_file)
    omoccurrences_countries = meta_load_omoccurrences_countries(omoccurrences_countries_file)
    sql_uri_src = meta_load_sql_uri_src(sql_config_file, "symbscan")

    # Create cache directory
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    taxonunits_fields_dtypes = table_fields["taxonunits"]
    taxonunits_field_names = taxonunits_fields_dtypes.keys()
    tbl_taxonunits = get_taxonunits_table(
        taxonunits_cache_file,
        sql_uri_src,
        taxonunits_field_names,
        taxonunits_fields_dtypes
    )

    omoccurrences_fields_dtypes = table_fields["omoccurrences"]
    omoccurrences_min = get_omoccurrences_min(
        omoccurrences_min_cache_file,
        sql_uri_src,
        omoccurrences_countries,
        omoccurrences_provinces,
        omoccurrences_latitude_range,
        omoccurrences_longitude_range,
        {k: v for k, v in omoccurrences_fields_dtypes.items() if k in ["occid", "collid", "tidinterpreted"]}
    )

    omcollections_fields_dtypes = table_fields["omcollections"]
    omcollections_field_names = omcollections_fields_dtypes.keys()
    tbl_omcollections = get_omcollections_table(
        omcollections_cache_file,
        sql_uri_src,
        omcollections_field_names,
        np.unique(omoccurrences_min["collid"]).astype(str).tolist(),
        omcollections_fields_dtypes
    )

    institutions_fields_dtypes = table_fields["institutions"]
    institutions_field_names = institutions_fields_dtypes.keys()
    tbl_institutions = get_institutions_table(
        institutions_cache_file,
        sql_uri_src,
        institutions_field_names,
        np.unique(tbl_omcollections["iid"][~pd.isna(tbl_omcollections["iid"])]).astype(str).tolist(),
        institutions_fields_dtypes
    )

    occurrence_tids = np.unique(
        omoccurrences_min["tidinterpreted"][~pd.isna(omoccurrences_min["tidinterpreted"])]
    ).astype(str).tolist()
    taxaenumtree_field_dtypes = table_fields["taxaenumtree"]
    taxaenumtree_field_names = table_fields["taxaenumtree"].keys()

    tbl_taxaenumtree = get_taxaenumtree_table(
        taxaenumtree_cache_file,
        sql_uri_src,
        taxaenumtree_field_names,
        occurrence_tids,
        taxaenumtree_field_dtypes
    )

    taxa_fields_dtypes = table_fields["taxa"]
    taxa_field_names = taxa_fields_dtypes.keys()
    all_taxa_tids = np.unique(tbl_taxaenumtree["tid"]).astype(str).tolist()
    tbl_taxa = get_taxa_table(
        taxa_cache_file,
        sql_uri_src,
        taxa_field_names,
        all_taxa_tids,
        taxa_fields_dtypes
    )

    if not os.path.exists(sqlite_outfile):
        sqlite_create_db(sqlite_create_file, sqlite_outfile)


if __name__ == "__main__":
    main()

