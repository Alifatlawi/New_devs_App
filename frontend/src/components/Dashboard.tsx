import React, { useEffect, useState } from "react";
import { RevenueSummary } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";
import type { DashboardProperty } from "../types/dashboard";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 6 }, (_, i) => CURRENT_YEAR - i);

// Default the year picker to the most recent year that has bookings, so picking a month
// doesn't land on an empty year (e.g. data from 2024 viewed in 2026).
const latestBookingYear = (properties: DashboardProperty[]): number =>
  properties.reduce<number | null>(
    (latest, p) => (p.latest_booking_year !== null && (latest === null || p.latest_booking_year > latest) ? p.latest_booking_year : latest),
    null,
  ) ?? CURRENT_YEAR;

const selectClassName =
  "block w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm bg-white disabled:bg-gray-100 disabled:text-gray-400";

const Dashboard: React.FC = () => {
  // The property list comes from the API, scoped to the signed-in tenant (no hard-coded IDs).
  const [properties, setProperties] = useState<DashboardProperty[]>([]);
  const [loadingProperties, setLoadingProperties] = useState(true);
  const [propertiesError, setPropertiesError] = useState('');
  const [selectedPropertyId, setSelectedPropertyId] = useState('');
  const [month, setMonth] = useState(''); // '' = all time, otherwise "1".."12"
  const [year, setYear] = useState(CURRENT_YEAR);

  useEffect(() => {
    let cancelled = false;
    SecureAPI.getDashboardProperties()
      .then((list) => {
        if (cancelled) return;
        setProperties(list);
        setSelectedPropertyId((current) => current || list[0]?.id || '');
        setYear(latestBookingYear(list));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        console.error(err);
        setPropertiesError('Failed to load your properties');
      })
      .finally(() => {
        if (!cancelled) setLoadingProperties(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProperty = properties.find((p) => p.id === selectedPropertyId);

  const renderContent = () => {
    if (loadingProperties) {
      return <div className="h-32 bg-gray-50 rounded-lg animate-pulse" aria-label="Loading properties" />;
    }
    if (propertiesError) {
      return <div className="p-4 text-red-600 bg-red-50 rounded-lg">{propertiesError}</div>;
    }
    if (properties.length === 0 || !selectedProperty) {
      return <div className="p-4 text-gray-600 bg-gray-50 rounded-lg">No properties found for your account.</div>;
    }
    return (
      <RevenueSummary
        propertyId={selectedProperty.id}
        year={month ? year : undefined}
        month={month ? Number(month) : undefined}
      />
    );
  };

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <div className="mb-6">
            <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-4">
              <div>
                <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
                <p className="text-sm lg:text-base text-gray-600">
                  Monthly performance insights for your properties
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <label className="flex flex-col text-xs font-medium text-gray-700 gap-1">
                  Property
                  <select
                    value={selectedPropertyId}
                    onChange={(e) => setSelectedPropertyId(e.target.value)}
                    disabled={properties.length === 0}
                    className={`${selectClassName} min-w-[200px]`}
                  >
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col text-xs font-medium text-gray-700 gap-1">
                  Month
                  <select value={month} onChange={(e) => setMonth(e.target.value)} className={selectClassName}>
                    <option value="">All time</option>
                    {MONTHS.map((name, i) => (
                      <option key={name} value={String(i + 1)}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col text-xs font-medium text-gray-700 gap-1">
                  Year
                  <select
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                    disabled={!month}
                    className={selectClassName}
                  >
                    {(YEARS.includes(year) ? YEARS : [year, ...YEARS]).map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            {selectedProperty && month && (
              <p className="mt-3 text-xs text-gray-500">
                Months follow the property's local time ({selectedProperty.timezone}), by check-in date.
              </p>
            )}
          </div>

          <div className="space-y-6">{renderContent()}</div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
