import React, { useEffect, useState } from 'react';
import { SecureAPI } from '../lib/secureApi';
import type { RevenueSummaryData } from '../types/dashboard';

interface RevenueSummaryProps {
    propertyId: string;
    /** Set year and month together for a monthly total; omit both for all time. */
    year?: number;
    month?: number;
}

const formatMoney = (amount: string, currency: string): string => {
    // The API has already rounded to cents; Number() is used for display formatting only, no arithmetic.
    try {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(amount));
    } catch {
        return `${currency} ${amount}`; // unknown currency code
    }
};

const formatPeriod = (year?: number, month?: number): string =>
    year !== undefined && month !== undefined
        ? new Date(Date.UTC(year, month - 1, 1)).toLocaleString(undefined, { month: 'long', year: 'numeric', timeZone: 'UTC' })
        : 'All time';

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({ propertyId, year, month }) => {
    const [data, setData] = useState<RevenueSummaryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        // Ignore a response that arrives after the user has switched property/period,
        // otherwise a slow request can overwrite the current selection with stale numbers.
        let cancelled = false;
        setLoading(true);
        setError('');

        const period = year !== undefined && month !== undefined ? { year, month } : null;
        SecureAPI.getDashboardSummary(propertyId, period)
            .then((response) => {
                if (!cancelled) setData(response);
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                console.error(err);
                setData(null);
                setError('Failed to load revenue data');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [propertyId, year, month]);

    if (loading) {
        return (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200" aria-label="Loading revenue">
                <div className="animate-pulse space-y-4">
                    <div className="h-4 bg-gray-100 rounded w-1/4"></div>
                    <div className="h-8 bg-gray-100 rounded w-1/2"></div>
                    <div className="flex gap-4 pt-4">
                        <div className="h-12 bg-gray-100 rounded flex-1"></div>
                        <div className="h-12 bg-gray-100 rounded flex-1"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) return <div className="p-4 text-red-600 bg-red-50 rounded-lg">{error}</div>;
    if (!data) return null;

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="p-6">
                <div className="mb-6">
                    <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                        Total Revenue · {formatPeriod(year, month)}
                    </h2>
                    <p className="text-3xl font-bold text-gray-900 tracking-tight mt-1 break-words">
                        {formatMoney(data.total_revenue, data.currency)}
                    </p>
                    {data.reservations_count === 0 && (
                        <p className="text-sm text-gray-500 mt-2">No reservations in this period.</p>
                    )}
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
                    <div>
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Property ID</p>
                        <p className="text-sm font-semibold text-gray-700 font-mono mt-1">{data.property_id}</p>
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Reservations</p>
                        <p className="text-sm font-semibold text-gray-700 mt-1">{data.reservations_count} <span className="font-normal text-gray-400">bookings</span></p>
                    </div>
                </div>
            </div>
        </div>
    );
};
