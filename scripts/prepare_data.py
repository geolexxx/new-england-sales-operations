#!/usr/bin/env python3
"""Prepare a source-backed New England sales-operations prospect dataset.

The script uses EPA GHGRP 2023 facility records and the corresponding
parent-company crosswalk. It intentionally targets decision-maker roles rather
than inventing individual names or contact details.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


NEW_ENGLAND_STATES = ["MA", "CT", "RI", "NH", "VT", "ME"]

STATE_POINTS = {
    "MA": 20,
    "CT": 16,
    "RI": 16,
    "NH": 16,
    "ME": 12,
    "VT": 12,
}

STATE_OWNERS = {
    "MA": "Sales Rep A - Massachusetts",
    "CT": "Sales Rep B - Connecticut/Rhode Island",
    "RI": "Sales Rep B - Connecticut/Rhode Island",
    "NH": "Sales Rep C - Northern New England",
    "ME": "Sales Rep C - Northern New England",
    "VT": "Sales Rep C - Northern New England",
}

SECTOR_RULES = {
    "Chemicals": {
        "fit": 28,
        "viability": 10,
        "target_role": "Plant Manager",
        "secondary_role": "Energy Procurement Manager",
        "campaign": "Industrial High-Load",
        "note": "Energy-intensive industrial facility; prioritize operational and procurement stakeholders.",
    },
    "Minerals": {
        "fit": 26,
        "viability": 10,
        "target_role": "Plant Manager",
        "secondary_role": "Director of Strategic Sourcing",
        "campaign": "Industrial High-Load",
        "note": "Industrial process-load prospect with potential power and natural-gas purchasing needs.",
    },
    "Other": {
        "fit": 22,
        "viability": 10,
        "target_role": "Director of Facilities",
        "secondary_role": "Energy and Sustainability Manager",
        "campaign": "Facilities and Institutions",
        "note": "General commercial or institutional facility; validate site portfolio and purchasing authority.",
    },
    "Other,Suppliers of CO2": {
        "fit": 20,
        "viability": 8,
        "target_role": "Director of Operations",
        "secondary_role": "Strategic Sourcing Manager",
        "campaign": "Industrial High-Load",
        "note": "Industrial supplier; validate whether energy procurement is managed at the site or parent-company level.",
    },
    "Other,Waste": {
        "fit": 21,
        "viability": 9,
        "target_role": "Director of Operations",
        "secondary_role": "Facilities Manager",
        "campaign": "Waste and Environmental",
        "note": "Mixed industrial and waste operation; confirm energy-load profile and site decision authority.",
    },
    "Petroleum and Natural Gas Systems": {
        "fit": 15,
        "viability": 7,
        "target_role": "Director of Operations",
        "secondary_role": "Energy Procurement Manager",
        "campaign": "Energy Infrastructure",
        "note": "Energy-sector operator; retain for market intelligence and qualify end-customer purchasing fit.",
    },
    "Power Plants": {
        "fit": 5,
        "viability": 0,
        "target_role": "Plant Manager",
        "secondary_role": "Director of Operations",
        "campaign": "Market Intelligence - Generation",
        "note": "Generation facility; low end-customer fit, retained for market context and qualification practice.",
    },
    "Power Plants,Waste": {
        "fit": 10,
        "viability": 3,
        "target_role": "Plant Manager",
        "secondary_role": "Director of Operations",
        "campaign": "Market Intelligence - Generation",
        "note": "Generation and waste facility; validate load-serving opportunity before outreach.",
    },
    "Pulp and Paper": {
        "fit": 30,
        "viability": 10,
        "target_role": "Energy Manager",
        "secondary_role": "Director of Procurement",
        "campaign": "Industrial High-Load",
        "note": "High-load manufacturing prospect with a clear energy-management and procurement use case.",
    },
    "Pulp and Paper,Waste": {
        "fit": 30,
        "viability": 10,
        "target_role": "Energy Manager",
        "secondary_role": "Director of Procurement",
        "campaign": "Industrial High-Load",
        "note": "High-load manufacturing and waste operation; prioritize energy and procurement stakeholders.",
    },
    "Waste": {
        "fit": 20,
        "viability": 9,
        "target_role": "Director of Operations",
        "secondary_role": "Facilities Manager",
        "campaign": "Waste and Environmental",
        "note": "Waste-sector facility; qualify electricity, natural-gas, and multi-site purchasing needs.",
    },
}

SCALE_THRESHOLDS = [
    (0, 10, "Small Reporting Load"),
    (50_000, 15, "Mid Reporting Load"),
    (100_000, 20, "Large Reporting Load"),
    (250_000, 25, "Very Large Reporting Load"),
    (500_000, 30, "Enterprise Reporting Load"),
]

EPA_DATASET_URL = "https://www.epa.gov/ghgreporting/data-sets"
EPA_PARENT_URL = (
    "https://www.epa.gov/system/files/other-files/2024-10/"
    "ghgp_data_parent_company.xlsb"
)
SOURCE_AS_OF_DATE = "2024-08-16"
RESEARCH_DATE = "2026-07-30"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def normalize_zip(value: object) -> str:
    if pd.isna(value):
        return ""
    raw = str(value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw.zfill(5)


def scale_rule(emissions: float) -> tuple[int, str]:
    selected = SCALE_THRESHOLDS[0]
    for threshold in SCALE_THRESHOLDS:
        if emissions >= threshold[0]:
            selected = threshold
    return selected[1], selected[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facility-xlsx", required=True)
    parser.add_argument("--parent-xlsx", required=True)
    parser.add_argument("--project-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_dir = Path(args.project_dir)
    raw_dir = project_dir / "data" / "raw"
    processed_dir = project_dir / "data" / "processed"
    salesforce_dir = project_dir / "salesforce"
    for directory in (raw_dir, processed_dir, salesforce_dir):
        directory.mkdir(parents=True, exist_ok=True)

    facility = pd.read_excel(
        args.facility_xlsx,
        sheet_name="Direct Point Emitters",
        header=3,
    )
    facility = facility[facility["State"].isin(NEW_ENGLAND_STATES)].copy()

    parent = pd.read_excel(args.parent_xlsx, sheet_name="2023")
    parent["PARENT CO. PERCENT OWNERSHIP"] = pd.to_numeric(
        parent["PARENT CO. PERCENT OWNERSHIP"], errors="coerce"
    ).fillna(0)
    parent = (
        parent.sort_values(
            ["GHGRP FACILITY ID", "PARENT CO. PERCENT OWNERSHIP"],
            ascending=[True, False],
        )
        .drop_duplicates("GHGRP FACILITY ID")
        .copy()
    )

    joined = facility.merge(
        parent[
            [
                "GHGRP FACILITY ID",
                "PARENT COMPANY NAME",
                "PARENT CO. PERCENT OWNERSHIP",
            ]
        ],
        left_on="Facility Id",
        right_on="GHGRP FACILITY ID",
        how="left",
    )

    rows: list[dict[str, object]] = []
    for _, source in joined.iterrows():
        sector = clean_text(source["Industry Type (sectors)"])
        rule = SECTOR_RULES[sector]
        emissions = float(source["Total reported direct emissions"])
        scale_points, scale_band = scale_rule(emissions)
        parent_name = clean_text(source["PARENT COMPANY NAME"])
        facility_name = clean_text(source["Facility Name"])
        city = clean_text(source["City"]).title()
        state = clean_text(source["State"]).upper()
        zip_code = normalize_zip(source["Zip Code"])
        naics = str(int(source["Primary NAICS Code"]))
        address = clean_text(source["Address"])
        facility_id = int(source["Facility Id"])

        data_quality_points = (
            (4 if parent_name else 0)
            + (2 if naics else 0)
            + (1 if city else 0)
            + (1 if pd.notna(source["Latitude"]) else 0)
            + (2 if rule["target_role"] else 0)
        )
        lead_score = (
            STATE_POINTS[state]
            + int(rule["fit"])
            + scale_points
            + data_quality_points
            + int(rule["viability"])
        )

        rows.append(
            {
                "External_ID": f"GHGRP-{facility_id}",
                "EPA_Facility_ID": facility_id,
                "Account_Name": f"{facility_name} - {city}, {state}",
                "Account_Site": facility_name,
                "Parent_Company": parent_name,
                "Parent_Ownership_Pct": float(
                    source["PARENT CO. PERCENT OWNERSHIP"]
                ),
                "Industry_Sector": sector,
                "NAICS_Code": naics,
                "City": city,
                "State": state,
                "ZIP_Code": zip_code,
                "Address": address,
                "County": clean_text(source["County"]).title(),
                "Latitude": float(source["Latitude"]),
                "Longitude": float(source["Longitude"]),
                "Total_Direct_Emissions_mtCO2e": emissions,
                "Operational_Scale_Band": scale_band,
                "Target_Decision_Maker_Role": str(rule["target_role"]),
                "Secondary_Decision_Maker_Role": str(rule["secondary_role"]),
                "Decision_Maker_Data_Type": (
                    "Role-based target; individual person not yet verified"
                ),
                "Campaign_Segment": str(rule["campaign"]),
                "Suggested_Owner": STATE_OWNERS[state],
                "Account_Research_Status": "Verified from EPA source",
                "Contact_Research_Status": "Role identified; person not yet verified",
                "Qualification_Notes": str(rule["note"]),
                "Facility_Source_URL": EPA_DATASET_URL,
                "Parent_Company_Source_URL": EPA_PARENT_URL,
                "Source_Dataset": "EPA GHGRP 2023 Direct Point Emitters",
                "Source_As_Of_Date": SOURCE_AS_OF_DATE,
                "Research_Date": RESEARCH_DATE,
                "State_Points_Reference": STATE_POINTS[state],
                "Sector_Points_Reference": int(rule["fit"]),
                "Scale_Points_Reference": scale_points,
                "Data_Quality_Points_Reference": data_quality_points,
                "Viability_Points_Reference": int(rule["viability"]),
                "Lead_Score_Reference": lead_score,
            }
        )

    clean = pd.DataFrame(rows)
    clean = clean.sort_values(
        [
            "Lead_Score_Reference",
            "Total_Direct_Emissions_mtCO2e",
            "EPA_Facility_ID",
        ],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    clean.insert(
        0,
        "Prospect_ID",
        [f"NE-{index:03d}" for index in range(1, len(clean) + 1)],
    )
    clean["Lead_Rank_Reference"] = range(1, len(clean) + 1)
    clean["Lead_Priority_Reference"] = clean["Lead_Rank_Reference"].map(
        lambda rank: "High" if rank <= 30 else ("Medium" if rank <= 80 else "Low")
    )

    assert len(clean) == 160
    assert clean["EPA_Facility_ID"].nunique() == 160
    assert (clean["Lead_Priority_Reference"] == "High").sum() == 30

    duplicate_indexes = [0, 31, 63, 95, 127]
    duplicates = clean.iloc[duplicate_indexes].copy()
    duplicates["Account_Name"] = duplicates["Account_Name"].map(
        lambda value: f"  {str(value).lower()}  "
    )
    duplicates["Synthetic_Duplicate"] = "Yes"
    duplicates["Duplicate_Scenario"] = (
        "Synthetic CRM duplicate with casing/spacing variation"
    )

    raw = clean.copy()
    raw["Synthetic_Duplicate"] = "No"
    raw["Duplicate_Scenario"] = ""
    raw = pd.concat([raw, duplicates], ignore_index=True)
    raw.insert(
        0,
        "Raw_Record_ID",
        [f"RAW-{index:03d}" for index in range(1, len(raw) + 1)],
    )

    dedupe_log = duplicates[
        [
            "External_ID",
            "EPA_Facility_ID",
            "Account_Name",
            "Duplicate_Scenario",
        ]
    ].copy()
    dedupe_log.insert(
        0,
        "Dedupe_Action",
        "Removed from cleaned prospect table using External_ID",
    )

    clean.to_csv(processed_dir / "new_england_prospects_clean.csv", index=False)
    raw.to_csv(raw_dir / "new_england_prospects_raw.csv", index=False)
    dedupe_log.to_csv(processed_dir / "deduplication_log.csv", index=False)

    account_import = clean[
        [
            "External_ID",
            "Account_Name",
            "Account_Site",
            "Parent_Company",
            "Industry_Sector",
            "Address",
            "City",
            "State",
            "ZIP_Code",
            "Target_Decision_Maker_Role",
            "Campaign_Segment",
            "Lead_Priority_Reference",
            "Qualification_Notes",
            "EPA_Facility_ID",
        ]
    ].copy()
    account_import.columns = [
        "GHGRP_Facility_ID__c",
        "Account Name",
        "Account Site",
        "Parent_Company__c",
        "Industry",
        "Billing Street",
        "Billing City",
        "Billing State/Province",
        "Billing Zip/Postal Code",
        "Target_Decision_Maker_Role__c",
        "Campaign_Segment__c",
        "Rating",
        "Description",
        "EPA_Facility_ID__c",
    ]
    account_import["Rating"] = account_import["Rating"].map(
        {"High": "Hot", "Medium": "Warm", "Low": "Cold"}
    )
    account_import.to_csv(
        salesforce_dir / "salesforce_accounts_import.csv", index=False
    )

    high = clean[clean["Lead_Priority_Reference"] == "High"].copy()
    campaign = high[
        [
            "External_ID",
            "Account_Name",
            "Campaign_Segment",
            "Suggested_Owner",
            "Lead_Priority_Reference",
        ]
    ].copy()
    campaign.insert(0, "Campaign_Name", "New England High-Priority Energy Prospects")
    campaign["Campaign_Member_Status"] = "Planned"
    campaign["Salesforce_Account_ID"] = ""
    campaign.to_csv(
        salesforce_dir / "salesforce_campaign_assignment_template.csv",
        index=False,
    )

    contact_queue = high[
        [
            "Prospect_ID",
            "Account_Name",
            "Parent_Company",
            "Target_Decision_Maker_Role",
            "Secondary_Decision_Maker_Role",
            "Suggested_Owner",
            "Facility_Source_URL",
        ]
    ].copy()
    contact_queue["Contact_Name"] = ""
    contact_queue["Contact_Title"] = ""
    contact_queue["Public_Profile_URL"] = ""
    contact_queue["Business_Email"] = ""
    contact_queue["Verification_Status"] = "Not Researched"
    contact_queue.to_csv(
        salesforce_dir / "high_priority_contact_research_queue.csv",
        index=False,
    )

    data_dictionary = pd.DataFrame(
        [
            (
                "External_ID",
                "Stable prospect key derived from the EPA GHGRP Facility ID.",
                "EPA",
            ),
            (
                "Account_Name",
                "Facility-level Salesforce account name with city and state.",
                "Derived",
            ),
            (
                "Parent_Company",
                "Highest-ownership parent reported in the EPA parent-company file.",
                "EPA",
            ),
            (
                "Operational_Scale_Band",
                "Scale proxy based on reported direct emissions; not employee count.",
                "Derived",
            ),
            (
                "Target_Decision_Maker_Role",
                "Role-based outreach target; not a verified individual contact.",
                "Derived",
            ),
            (
                "Lead_Score_Reference",
                "0-100 score using geography, sector, scale, data quality, and viability.",
                "Derived",
            ),
            (
                "Lead_Priority_Reference",
                "Top 30 scored accounts are High, ranks 31-80 Medium, remainder Low.",
                "Derived",
            ),
        ],
        columns=["Field", "Definition", "Source_Type"],
    )
    data_dictionary.to_csv(processed_dir / "data_dictionary.csv", index=False)

    payload = {
        "records": clean.to_dict(orient="records"),
        "raw_records": raw.to_dict(orient="records"),
        "dedupe_records": dedupe_log.to_dict(orient="records"),
        "rules": {
            "state_points": STATE_POINTS,
            "sector_rules": SECTOR_RULES,
            "scale_thresholds": [
                {
                    "minimum": threshold,
                    "points": points,
                    "label": label,
                }
                for threshold, points, label in SCALE_THRESHOLDS
            ],
            "high_priority_count": 30,
            "medium_priority_max_rank": 80,
        },
    }
    with (processed_dir / "workbook_payload.json").open(
        "w", encoding="utf-8"
    ) as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)

    print(
        json.dumps(
            {
                "raw_rows": len(raw),
                "clean_rows": len(clean),
                "duplicates_removed": len(duplicates),
                "high_priority_rows": int(
                    (clean["Lead_Priority_Reference"] == "High").sum()
                ),
                "states": sorted(clean["State"].unique().tolist()),
                "output_dir": str(project_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
