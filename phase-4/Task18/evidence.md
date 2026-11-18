# Task 18 evidence

## Implementation evidence

- [kpi_explorer.py](kpi_explorer.py) exposes governed catalog metrics through a
  Streamlit page.
- `ROLE_RULES` limits each demo role to approved metrics and dimensions.
- `_minimum_group_size` enforces the catalog threshold and the five-record
  privacy floor.
- The query filters `group_size >= minimum_size` before any table is rendered.
- The page wrapper at `pages/12_KPI_Explorer.py` makes the explorer discoverable
  in the Streamlit multipage application.

## Break-it results

| Scenario | Expected safe result | Result |
| --- | --- | --- |
| Manager selects payroll metric | Metric unavailable | Blocked by role metric set |
| Manager selects Company or Department | Dimension unavailable | Blocked by role dimension set |
| Non-delivery metric at Team level | No invented team value | Warning and return |
| Group has fewer than five records | No displayed value | Filtered before rendering |
| Catalog requires 10 records | Five-record value must not override it | Ten-record threshold retained |

## Automated validation

`test_kpi_explorer.py` covers:

- minimum privacy floor and catalog threshold handling;
- distinct role metric/dimension permissions;
- role-filtered metric lists;
- latest-period company aggregation;
- latest-period group selection.

The source compiles and the focused test suite passes against the current
repository environment.
