# Salesforce build notes

## Account fields configured

| Field label | API name | Type | Use |
|---|---|---|---|
| GHGRP Facility ID | `GHGRP_Facility_ID__c` | Text, Unique, External ID | Account upsert and deduplication key |
| Parent Company | `Parent_Company__c` | Text | Parent-company research field |
| Target Decision Maker Role | `Target_Decision_Maker_Role__c` | Text | Role-based outreach planning |
| Campaign Segment | `Campaign_Segment__c` | Text/Picklist | Prospect-list segmentation |
| EPA Industry Sector | `EPA_Industry_Sector__c` | Text/Picklist | Industry reporting and filtering |

## Import workflow completed

1. Created the custom Account fields in a Salesforce Developer Org.
2. Tested five records with
   `salesforce_accounts_import_sample.csv`.
3. Mapped all 14 CSV columns to standard or custom Account fields.
4. Selected **Add new and update existing records** and matched Accounts using
   `GHGRP_Facility_ID__c`.
5. Corrected the billing-address import format by supplying full state and
   country names.
6. Upserted `salesforce_accounts_import_160.csv`.
7. Verified the completed job: **160 records processed, 0 failed**.

## Reporting completed

- Five Account list views representing the campaign segments.
- `Prospects by Campaign Segment` summary report.
- `Prospects by Rating` summary report.
- `High-Priority Prospects by State` summary report.
- Dashboard with:
  - total prospects: 160;
  - high-priority prospects: 30;
  - campaign-segment distribution;
  - priority distribution; and
  - high-priority accounts by state.

## Data-model limitation

The project imports facility-level Accounts only. Target decision-maker values
represent job functions such as Energy Manager or Director of Facilities; they
are not Salesforce Contact records and do not identify individual people.
