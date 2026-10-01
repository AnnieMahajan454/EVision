"""Reference data for the simulated fleet: vehicle models, city climates and usage profiles."""

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VehicleModel:
    make: str
    model: str
    wmi: str  # VIN world-manufacturer identifier
    capacity_kwh: float
    rated_range_km: float  # ARAI / MIDC certified
    base_efficiency_wh_km: float  # real-world consumption at ~45 km/h, 24 C
    nominal_voltage_v: float
    ac_max_kw: float
    dc_max_kw: float


CATALOG = [
    VehicleModel("Tata", "Nexon EV", "MAT", 40.5, 465, 128, 320, 7.2, 50),
    VehicleModel("Tata", "Tiago EV", "MAT", 24.0, 315, 108, 320, 3.3, 25),
    VehicleModel("Tata", "Punch EV", "MAT", 35.0, 421, 118, 320, 7.2, 50),
    VehicleModel("Mahindra", "XUV400", "MA1", 39.4, 456, 140, 380, 7.2, 50),
    VehicleModel("MG", "ZS EV", "MZ7", 50.3, 461, 150, 420, 7.4, 50),
    VehicleModel("Hyundai", "Ioniq 5", "MAL", 72.6, 631, 158, 697, 11.0, 150),
    VehicleModel("BYD", "Atto 3", "LGX", 60.5, 521, 148, 400, 7.0, 80),
]


@dataclass(frozen=True)
class City:
    name: str
    annual_mean_c: float
    seasonal_amplitude_c: float
    hottest_day_of_year: int
    diurnal_swing_c: float

    def temperature(self, when: datetime) -> float:
        """Smooth seasonal + daily cycle (warmest mid-afternoon)."""
        doy = when.timetuple().tm_yday
        seasonal = self.seasonal_amplitude_c * math.cos(2 * math.pi * (doy - self.hottest_day_of_year) / 365)
        hour = when.hour + when.minute / 60
        diurnal = self.diurnal_swing_c * math.sin(2 * math.pi * (hour - 9) / 24)
        return self.annual_mean_c + seasonal + diurnal


CITIES = [
    City("Bengaluru", 24.5, 3.0, 110, 5.0),
    City("Chennai", 29.5, 3.5, 140, 4.0),
    City("Delhi", 25.5, 9.0, 160, 6.0),
    City("Mumbai", 28.0, 2.0, 130, 3.0),
    City("Hyderabad", 27.0, 4.5, 125, 5.5),
    City("Pune", 25.0, 4.0, 110, 6.0),
]


@dataclass(frozen=True)
class UsageProfile:
    name: str
    label: str  # used in the vehicle nickname
    daily_km: float  # long-run average, used to back-fill odometer history
    charging_habit: str
    dc_fast_share: float  # expected long-run share of energy from DC fast charging
    high_soc_share: float  # expected share of sessions that end at >= 95 %
    battery_heat_c: float  # how much warmer than ambient the pack runs on average


PROFILES = {
    # Office commuters who schedule charging for the off-peak window (smart wallbox).
    "commuter_smart": UsageProfile("commuter_smart", "Commute", 42, "scheduled_offpeak", 0.04, 0.05, 3.5),
    # Commuters who plug in as soon as they get home and always charge to 100 %.
    "commuter_plugin": UsageProfile("commuter_plugin", "Commute", 42, "plug_in_on_arrival", 0.04, 0.90, 3.5),
    # No home charger: relies on public DC fast chargers and the occasional workplace AC point.
    "commuter_public": UsageProfile("commuter_public", "Commute", 38, "public_only", 0.75, 0.25, 5.0),
    # Field sales: daily intercity legs at highway speed.
    "sales": UsageProfile("sales", "Sales", 110, "plug_in_on_arrival", 0.20, 0.85, 5.0),
    # Ride-hailing cabs: many short city trips, midday DC top-ups, overnight depot AC.
    "ride_hailing": UsageProfile("ride_hailing", "Cab", 165, "depot", 0.35, 0.10, 6.0),
}

# Default fleet mix for 20 vehicles; scaled proportionally for other sizes.
FLEET_MIX = {
    "commuter_smart": 5,
    "commuter_plugin": 4,
    "commuter_public": 3,
    "sales": 3,
    "ride_hailing": 5,
}
