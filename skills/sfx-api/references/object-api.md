# SFX object API coverage

The command wrapper uses these `/v2` paths from the supplied OpenAPI specifications.

| CLI resource | API path | Get | Create | Update | Delete | Export |
| --- | --- | --- | --- | --- | --- | --- |
| `navigator` | `/navigator` | documented GET | documented POST | documented PUT | documented DELETE | `/navigator/{id}/export` |
| `detector` | `/detector` | documented GET | documented POST | documented PUT | documented DELETE | `/detector/{id}/export` |
| `datalink` | `/crosslink` | documented GET | documented POST | documented PUT | documented DELETE | same representation as GET |
| `dashboard-group` | `/dashboardgroup` | documented GET | documented POST | documented PUT | documented DELETE | `/dashboardgroup/{id}/export` |
| `chart` | `/chart` | documented GET | documented POST | documented PUT | documented DELETE | same representation as GET |
| `dashboard` | `/dashboard` | documented GET | documented POST | documented PUT | documented DELETE | same representation as GET |

Dedicated export routes for navigators, detectors, and dashboard groups are retained from the repository's established synchronization services. The supplied OpenAPI documents do not declare dedicated export routes for data links, charts, or dashboards.

Navigator create and update requests use `application/vnd.splunk.observability.navigator+json`. Other object mutations use `application/json`.
