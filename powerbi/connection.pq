// Power Query (M) used for every table in the EVision report.
//
// 1. Home -> Transform data -> Manage Parameters -> New:
//      PgServer   (Text)  e.g. localhost:5432
//      PgDatabase (Text)  e.g. evision
// 2. For each view below create a Blank Query, paste this, and change ViewName.
//    (Or use Get data -> PostgreSQL database once and pick the views from the
//     "analytics" schema in the Navigator – the steps are equivalent.)

let
    ViewName = "fact_trip",
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    View = Source{[Schema = "analytics", Item = ViewName]}[Data]
in
    View

// Views to import (all in schema "analytics"):
//   dim_vehicle, dim_date, dim_hour,
//   fact_trip, fact_vehicle_daily, fact_charging_session, fact_battery_health,
//   fact_range_prediction, fact_battery_health_forecast
