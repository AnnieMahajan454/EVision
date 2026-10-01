"""Physics-flavoured simulation of an Indian EV fleet.

Each vehicle is simulated minute by minute while driving. Consumption depends on speed
(aerodynamics, plus stop-go losses at low speed), on ambient temperature (air-conditioning
load) and on the driver. Charging follows the owner's habit. AC charging runs at constant
power; DC charging tapers above 50/80/90% SoC. Battery capacity fades with calendar age
(faster when hot) and with energy throughput (faster with DC fast charging and frequent
100% charges). The BMS reports the resulting state of health with a small per-vehicle bias.

The output has the same shape as the platform's public API payloads.
"""

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from simulator.catalog import CATALOG, CITIES, FLEET_MIX, PROFILES, City, UsageProfile, VehicleModel

IST = ZoneInfo("Asia/Kolkata")
VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"

# Degradation model (state of health, %).
CALENDAR_FADE_PER_SQRT_YEAR = 1.6
HEAT_ACCELERATION_PER_C = 0.05
CYCLE_FADE_PER_EFC = 0.012
DC_FAST_STRESS = 0.8
HIGH_SOC_STRESS = 0.4

HOME_CHARGER_KW = 7.2
PUBLIC_AC_KW = 7.4
DC_STATION_KW = 60.0
PUBLIC_AC_TARIFF = 14.0  # INR/kWh
DC_FAST_TARIFF = 21.0  # INR/kWh incl. GST


@dataclass
class SimulatedVehicle:
    vin: str
    nickname: str
    spec: VehicleModel
    profile: UsageProfile
    city: City
    registered_on: date
    driver_factor: float
    bms_bias: float
    long_run_battery_temp_c: float
    # Mutable state
    odometer_km: float
    efc: float  # equivalent full cycles of energy throughput
    soc: float
    battery_temp_c: float
    busy_until: datetime
    readings: list[dict] = field(default_factory=list)
    sessions: list[dict] = field(default_factory=list)

    def api_payload(self) -> dict:
        return {
            "vin": self.vin,
            "nickname": self.nickname,
            "make": self.spec.make,
            "model": self.spec.model,
            "model_year": self.registered_on.year,
            "battery_capacity_kwh": self.spec.capacity_kwh,
            "rated_range_km": self.spec.rated_range_km,
            "registered_on": self.registered_on.isoformat(),
        }

    def soh(self, on: date) -> float:
        age_years = max((on - self.registered_on).days, 0) / 365
        heat = max(self.long_run_battery_temp_c - 25, 0)
        calendar = CALENDAR_FADE_PER_SQRT_YEAR * math.sqrt(age_years) * (1 + HEAT_ACCELERATION_PER_C * heat)
        stress = (
            1 + DC_FAST_STRESS * self.profile.dc_fast_share + HIGH_SOC_STRESS * self.profile.high_soc_share
        )
        cycle = CYCLE_FADE_PER_EFC * self.efc * stress
        return 100 - calendar - cycle

    def usable_kwh(self, on: date) -> float:
        return self.spec.capacity_kwh * self.soh(on) / 100


class FleetSimulator:
    def __init__(self, n_vehicles: int, start: date, days: int, seed: int = 7):
        self.rng = np.random.default_rng(seed)
        self.start = start
        self.days = days
        self.vehicles = [self._make_vehicle(i, name) for i, name in enumerate(self._profile_mix(n_vehicles))]

    # --- setup ---------------------------------------------------------------------------

    @staticmethod
    def _profile_mix(n: int) -> list[str]:
        total = sum(FLEET_MIX.values())
        names = [name for name, count in FLEET_MIX.items() for _ in range(round(count * n / total))]
        while len(names) < n:
            names.append("commuter_smart")
        return names[:n]

    def _vin(self, wmi: str, year: int) -> str:
        year_code = "ABCDEFGHJKLMNPRSTVWXY123456789"[(year - 2010) % 30]
        body = "".join(self.rng.choice(list(VIN_CHARS), 5))
        serial = "".join(str(d) for d in self.rng.integers(0, 10, 6))
        return f"{wmi}{body}{year_code}C{serial}"[:17].ljust(17, "0")

    def _make_vehicle(self, index: int, profile_name: str) -> SimulatedVehicle:
        profile = PROFILES[profile_name]
        # Cabs and sales cars skew to cheaper, longer-range models.
        weights = np.array([3, 2, 2, 2, 1.5, 0.6, 1.0])
        if profile.name == "ride_hailing":
            weights = np.array([4, 2, 2, 1.5, 1, 0, 0.5])
        spec = CATALOG[self.rng.choice(len(CATALOG), p=weights / weights.sum())]
        city = CITIES[self.rng.integers(len(CITIES))]
        age_days = int(self.rng.integers(60, 1000))
        registered_on = self.start - timedelta(days=age_days)
        driver_factor = float(self.rng.normal(1.0, 0.06))

        history_km = age_days * profile.daily_km * float(self.rng.uniform(0.8, 1.2))
        typical_eff = spec.base_efficiency_wh_km * driver_factor * 1.08
        vehicle = SimulatedVehicle(
            vin=self._vin(spec.wmi, registered_on.year),
            nickname=f"{profile.label} {index + 1:02d} ({city.name})",
            spec=spec,
            profile=profile,
            city=city,
            registered_on=registered_on,
            driver_factor=driver_factor,
            bms_bias=float(self.rng.normal(0, 0.25)),
            long_run_battery_temp_c=city.annual_mean_c + profile.battery_heat_c,
            odometer_km=round(history_km, 1),
            efc=history_km * typical_eff / 1000 / spec.capacity_kwh,
            soc=float(self.rng.uniform(55, 85)),
            battery_temp_c=city.annual_mean_c,
            busy_until=datetime.combine(self.start, time(0), tzinfo=IST),
        )
        return vehicle

    # --- physics -------------------------------------------------------------------------

    @staticmethod
    def speed_factor(speed_kph: float) -> float:
        """Relative consumption vs. ~45 km/h: stop-go losses below, aero drag above."""
        return 0.9 + 0.00008 * (speed_kph - 45) ** 2 + 3 / max(speed_kph, 5)

    @staticmethod
    def climate_factor(ambient_c: float) -> float:
        """Air-conditioning (and the occasional heater) load."""
        return 1 + 0.012 * max(ambient_c - 24, 0) + 0.015 * max(18 - ambient_c, 0)

    def _reading(self, v: SimulatedVehicle, when: datetime, speed: float, power_kw: float, ambient: float):
        soh_reported = round(v.soh(when.date()) + v.bms_bias + float(self.rng.normal(0, 0.08)), 1)
        voltage = v.spec.nominal_voltage_v * (0.9 + 0.2 * v.soc / 100)
        current = power_kw * 1000 / voltage
        v.readings.append(
            {
                "recorded_at": when.isoformat(),
                "odometer_km": round(v.odometer_km, 2),
                "speed_kph": round(speed, 1),
                "soc_pct": round(min(max(v.soc, 0), 100), 1),
                "soh_pct": min(soh_reported, 100.0),
                "battery_voltage_v": round(voltage - 0.04 * current, 1),
                "battery_current_a": round(current, 1),
                "battery_temp_c": round(v.battery_temp_c, 1),
                "motor_temp_c": round(ambient + 10 + 0.35 * speed + float(self.rng.normal(0, 1.5)), 1),
                "ambient_temp_c": round(ambient + float(self.rng.normal(0, 0.4)), 1),
            }
        )

    def drive(self, v: SimulatedVehicle, depart: datetime, distance_km: float, mean_speed: float) -> datetime:
        """Simulate one trip at 1-minute resolution; returns the arrival time."""
        now = max(depart, v.busy_until + timedelta(minutes=8))
        ambient = v.city.temperature(now)
        v.battery_temp_c = ambient + 1.5  # pack has been parked
        trip_noise = float(self.rng.normal(1.0, 0.04))
        travelled = 0.0
        self._reading(v, now, 0.0, 1.0, ambient)

        while travelled < distance_km - 1e-6:
            ambient = v.city.temperature(now)
            speed = mean_speed * (1 + 0.22 * float(self.rng.normal()))
            if mean_speed < 45 and self.rng.random() < 0.12:  # traffic signal / jam
                speed = float(self.rng.uniform(0, 6))
            speed = float(np.clip(speed, 0, 125))
            km = min(speed / 60, distance_km - travelled)

            eff = (
                v.spec.base_efficiency_wh_km
                * v.driver_factor
                * self.speed_factor(max(speed, 1))
                * self.climate_factor(ambient)
                * trip_noise
            )
            energy_kwh = km * eff / 1000 + (0.02 if speed < 1 else 0)  # AC still running in a jam
            v.soc -= energy_kwh / v.usable_kwh(now.date()) * 100
            v.efc += energy_kwh / v.spec.capacity_kwh
            power_kw = energy_kwh * 60
            v.battery_temp_c += (ambient + 2 + 0.12 * power_kw - v.battery_temp_c) * 0.05
            v.odometer_km += km
            travelled += km
            now += timedelta(minutes=1)
            self._reading(v, now, speed, power_kw, ambient)

        v.busy_until = now
        return now

    def charge(self, v: SimulatedVehicle, start: datetime, charger: str, target_soc: float) -> datetime:
        start = max(start, v.busy_until + timedelta(minutes=3))
        if target_soc <= v.soc + 1:
            return start
        usable = v.usable_kwh(start.date())
        start_soc = v.soc
        battery_kwh = (target_soc - start_soc) / 100 * usable

        if charger == "dc_fast":
            station_kw = min(DC_STATION_KW, v.spec.dc_max_kw)
            hours, soc = 0.0, start_soc
            while soc < target_soc:
                step = min(1.0, target_soc - soc)
                taper = 1.0 if soc < 50 else 0.85 if soc < 80 else 0.45 if soc < 90 else 0.25
                hours += step / 100 * usable / (station_kw * taper)
                soc += step
            grid_kwh = battery_kwh / 0.93
            max_kw = station_kw
            cost = round(grid_kwh * DC_FAST_TARIFF, 2)
            v.battery_temp_c += 8
        else:
            max_kw = min(HOME_CHARGER_KW if charger == "home_ac" else PUBLIC_AC_KW, v.spec.ac_max_kw)
            grid_kwh = battery_kwh / 0.90
            hours = grid_kwh / max_kw
            cost = round(grid_kwh * PUBLIC_AC_TARIFF, 2) if charger == "public_ac" else None

        end = start + timedelta(hours=hours) + timedelta(seconds=int(self.rng.integers(30, 240)))
        v.soc = target_soc
        v.busy_until = end
        v.sessions.append(
            {
                "started_at": start.isoformat(),
                "ended_at": end.isoformat(),
                "charger_type": charger,
                "start_soc_pct": round(start_soc, 1),
                "end_soc_pct": round(target_soc, 1),
                "energy_delivered_kwh": round(grid_kwh, 2),
                "max_power_kw": max_kw,
                "cost_inr": cost,
            }
        )
        return end

    # --- daily behaviour -----------------------------------------------------------------

    def _at(self, day: date, hour: float, jitter_min: float = 0) -> datetime:
        minutes = hour * 60 + float(self.rng.normal(0, jitter_min)) if jitter_min else hour * 60
        return datetime.combine(day, time(0), tzinfo=IST) + timedelta(minutes=round(minutes))

    def _plan_trips(self, v: SimulatedVehicle, day: date) -> list[tuple[datetime, float, float]]:
        weekend = day.weekday() >= 5
        r = self.rng
        trips: list[tuple[datetime, float, float]] = []
        name = v.profile.name

        if name.startswith("commuter"):
            if not weekend:
                km = float(r.uniform(9, 26))
                trips.append((self._at(day, 8.6, 25), km, float(r.uniform(22, 38))))
                trips.append(
                    (self._at(day, 18.4, 35), km * float(r.uniform(0.95, 1.1)), float(r.uniform(20, 34)))
                )
                if r.random() < 0.25:
                    trips.append((self._at(day, 20.5, 30), float(r.uniform(3, 10)), float(r.uniform(20, 32))))
            elif r.random() < 0.08:  # weekend road trip
                trips.append((self._at(day, 7.5, 40), float(r.uniform(70, 120)), float(r.uniform(65, 90))))
                trips.append((self._at(day, 16.5, 50), float(r.uniform(70, 120)), float(r.uniform(65, 90))))
            else:
                for hour in sorted(r.uniform(10, 20, int(r.integers(0, 3)))):
                    trips.append((self._at(day, hour), float(r.uniform(4, 25)), float(r.uniform(22, 50))))
        elif name == "sales":
            if not weekend:
                out = float(r.uniform(40, 110))
                trips.append((self._at(day, 8.0, 30), float(r.uniform(5, 12)), float(r.uniform(22, 35))))
                trips.append((self._at(day, 9.5, 30), out, float(r.uniform(60, 88))))
                trips.append(
                    (self._at(day, 15.0, 45), out * float(r.uniform(0.9, 1.1)), float(r.uniform(60, 88)))
                )
            elif r.random() < 0.5:
                trips.append((self._at(day, 11, 60), float(r.uniform(5, 20)), float(r.uniform(22, 40))))
        else:  # ride hailing
            cursor = self._at(day, 7.5, 20)
            for _ in range(int(r.integers(8, 13))):
                km = float(r.uniform(5, 22))
                speed = float(r.uniform(18, 36))
                trips.append((cursor, km, speed))
                cursor += timedelta(minutes=km / speed * 60 + float(r.uniform(15, 50)))
                if cursor.hour >= 22:
                    break
        return trips

    def _simulate_day(self, v: SimulatedVehicle, day: date) -> None:
        habit = v.profile.charging_habit
        arrival = None
        usable = v.usable_kwh(day)
        worst_case_wh_km = v.spec.base_efficiency_wh_km * 1.4
        max_leg_km = 0.6 * usable * 1000 / worst_case_wh_km  # small-pack cars do shorter legs

        for depart, km, speed in self._plan_trips(v, day):
            km = min(km, max_leg_km)
            needed = km * worst_case_wh_km / 1000 / usable * 100
            if v.soc - needed < 12:
                # Not enough charge for this leg: stop at a public fast charger first.
                target = float(min(max(self.rng.uniform(80, 92), needed + 20), 100))
                depart = self.charge(v, depart - timedelta(minutes=40), "dc_fast", target)
            arrival = self.drive(v, depart, km, speed)

            if habit == "depot" and 11 <= arrival.hour <= 16 and v.soc < 35:
                self.charge(v, arrival + timedelta(minutes=5), "dc_fast", float(self.rng.uniform(78, 85)))
            if (
                habit == "public_only"
                and arrival.hour < 11
                and day.weekday() < 5
                and v.soc < 70
                and self.rng.random() < 0.3
            ):
                self.charge(v, arrival + timedelta(minutes=10), "public_ac", 90)

        evening = arrival or self._at(day, 19, 30)
        if habit == "scheduled_offpeak":
            if v.soc < 70 or self.rng.random() < 0.25:
                scheduled = datetime.combine(day, time(23, 0), tzinfo=IST)
                target = 90.0 if day.weekday() == 4 else 80.0
                self.charge(v, max(scheduled, evening + timedelta(minutes=5)), "home_ac", target)
        elif habit == "plug_in_on_arrival":
            if v.soc < 85:
                self.charge(v, evening + timedelta(minutes=float(self.rng.uniform(5, 25))), "home_ac", 100.0)
        elif habit == "public_only":
            if v.soc < 35:
                self.charge(v, evening + timedelta(minutes=15), "dc_fast", float(self.rng.uniform(82, 96)))
        elif habit == "depot":
            self.charge(v, evening + timedelta(minutes=20), "home_ac", 90.0)

    def run(self, progress=None) -> list[SimulatedVehicle]:
        for offset in range(self.days):
            day = self.start + timedelta(days=offset)
            for vehicle in self.vehicles:
                self._simulate_day(vehicle, day)
            if progress:
                progress(offset + 1, self.days)
        return self.vehicles
