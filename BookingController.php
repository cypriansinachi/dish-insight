<?php
namespace App\Http\Controllers;

use App\Models\AgentHotelServiceRequest; // Model for agent_bookings
use App\Models\AgentRestaurantTableReservation;
use App\Models\Booking;
use App\Models\Category;
use App\Models\Social\Events\UserEvent;
use Illuminate\Http\Request;
use Illuminate\Pagination\LengthAwarePaginator;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

class BookingController extends Controller
{

    /**
     * Get active bookings, reservations, and events for the authenticated user
     *
     * Query Parameters:
     * - events_only (boolean): If true, returns only active center events
     * - search (string): Search term for filtering
     * - from_date (string): Start date filter
     * - to_date (string): End date filter
     * - per_page (int): Number of items per page
     * - earliest_date (boolean): Sort by earliest date first
     * - status (string): Filter events by status (draft, published, closed)
     *
     * @param Request $request
     * @return \Illuminate\Http\JsonResponse
     */
    private const CACHE_DURATION = 10; // 10 minutes cache
    private const CACHE_PREFIX   = 'active_bookings_';

    /**
     * Get active bookings, reservations, and events for the authenticated user
     */
    public function getActiveBookings(Request $request)
    {

        $userId = auth()->id();

        // Generate cache key based on request parameters and user ID
        $cacheKey = $this->generateCacheKey($request, $userId);

        // Check if we should bypass cache (for real-time data needs)
        $bypassCache = $request->input('bypass_cache', false) || $request->input('test') === 'true';

        if (! $bypassCache) {
            $cachedResult = Cache::get($cacheKey);
            if ($cachedResult) {
                Log::info('Cache hit for active bookings', ['user_id' => $userId, 'cache_key' => $cacheKey]);
                return response()->json($cachedResult);
            }
        }

        Log::info('Cache miss for active bookings, generating fresh data', ['user_id' => $userId]);

        // Process the request
        $result = $this->processActiveBookings($request);

        // Cache the result (only cache successful responses)
        if ($result->getStatusCode() === 200 && ! $bypassCache) {
            $cacheData = $result->getData(true);
            Cache::put($cacheKey, $cacheData, now()->addMinutes(self::CACHE_DURATION));
            Log::info('Cached active bookings data', ['user_id' => $userId, 'cache_key' => $cacheKey]);
        }

        return $result;
    }

    /**
     * Generate cache key based on request parameters
     */
    private function generateCacheKey(Request $request, $userId): string
    {
        $keyParams = [
            'user_id'       => $userId,
            'events_only'   => $request->input('events_only', false),
            'search'        => $request->input('search', ''),
            'from_date'     => $request->input('from_date', ''),
            'to_date'       => $request->input('to_date', ''),
            'booking_type'  => $request->input('booking_type', ''),
            'status'        => $request->input('status', ''),
            'per_page'      => $request->input('per_page', 10),
            'earliest_date' => $request->input('earliest_date', false),
            'page'          => $request->input('page', 1),
        ];

        return self::CACHE_PREFIX . md5(serialize($keyParams));
    }

    /**
     * Process active bookings (main logic separated for caching)
     */
    private function processActiveBookings(Request $request)
    {
        // Remove excessive debug logging - keep only essential logs
        Log::info('Processing active bookings', [
            'user_id'     => auth()->id(),
            'events_only' => $request->input('events_only'),
        ]);

        // Temporary test return - remove this after testing
        if ($request->input('test') === 'true') {
            return response()->json([
                'status'  => 'test',
                'message' => 'Method is being called',
                'user_id' => auth()->id(),
            ]);
        }

        $today        = Carbon::today();
        $userId       = auth()->id();
        $perPage      = $request->input('per_page', 10);
        $search       = trim($request->input('search', ''));
        $bookingType  = $request->input('booking_type');
        $fromDate     = $request->input('from_date');
        $toDate       = $request->input('to_date', $fromDate);
        $filterBy     = $request->input('filter_by', 'day');
        $earliestFlag = filter_var($request->input('earliest_date', false), FILTER_VALIDATE_BOOLEAN);
        $eventsOnly   = filter_var($request->input('events_only', false), FILTER_VALIDATE_BOOLEAN);
        $eventStatus  = $request->input('status');

        // Fast path: when events_only=true, use optimized events-only query
        if ($eventsOnly) {
            return $this->getEventsOnly($request, $perPage, $search, $fromDate, $toDate, $filterBy, $earliestFlag, $eventStatus);
        }

        // Pre-calculate date ranges to avoid repeated calculations
        $dateRange = $this->calculateDateRange($fromDate, $toDate, $filterBy);

        // Execute queries in parallel using Laravel's collection (optimized)
        $results = collect([
            'bookings'     => $this->getBookingsData($userId, $search, $bookingType, $dateRange, $perPage, $earliestFlag, $today),
            'reservations' => $this->getReservationsData($userId, $search, $dateRange, $perPage, $earliestFlag, $today),
            'events'       => $this->getEventsData($userId, $search, $dateRange, $perPage, $earliestFlag, $eventStatus, $today, $request),
        ]);

        // Process data efficiently
        $bookingsData     = $this->processBookingsData($results['bookings']);
        $reservationsData = $this->processReservationsData($results['reservations']);
        $eventsData       = $this->processEventsData($results['events'], false);

        $mergedData = $bookingsData->merge($reservationsData)->merge($eventsData)
            ->sortBy('created_at', SORT_REGULAR, $earliestFlag);

        // Calculate pagination
        $totalItems  = $results['bookings']->total() + $results['reservations']->total() + $results['events']->total();
        $currentPage = $results['bookings']->currentPage();
        $lastPage    = max($results['bookings']->lastPage(), $results['reservations']->lastPage(), $results['events']->lastPage());

        return response()->json([
            'status'  => 'success',
            'message' => 'Bookings retrieved successfully',
            'data'    => [
                'bookings'   => $mergedData->values(),
                'pagination' => [
                    'current_page' => $currentPage,
                    'per_page'     => $perPage,
                    'total'        => $totalItems,
                    'last_page'    => $lastPage,
                ],
            ],
        ]);
    }

    /**
     * Optimized events-only path
     */
    private function getEventsOnly(Request $request, $perPage, $search, $fromDate, $toDate, $filterBy, $earliestFlag, $eventStatus)
    {

        $userId    = auth()->id();
        $userEmail = auth()->user()->email;
        $dateRange = $this->calculateDateRange($fromDate, $toDate, $filterBy);

        $eventsQuery = UserEvent::where(function ($q) use ($userId, $userEmail) {
            $q->where('user_id', $userId)
                ->orWhereHas('guestsList', function ($q) use ($userId) {
                    $q->where('user_id', $userId);
                })
                ->orWhereHas('cohost', function ($q) use ($userEmail) {
                    $q->where('email', $userEmail);
                });
        })
            ->whereHas('dates', function ($query) {
                $query->where('date', '>', now()->toDateString())
                    ->orWhere(function ($q) {
                        $q->where('date', '=', now()->toDateString())
                            ->where('start_time', '>=', now()->format('H:i:s'));
                    });
            })

            ->with($this->optimizedUserEventRelationships()) // Use optimized relationships
            ->when($eventStatus, fn($q) => $q->where('status', $eventStatus))
            ->when($search, function ($query) use ($search) {
                $query->where(function ($q) use ($search) {
                    $q->where('title', 'LIKE', "%$search%")
                        ->orWhere('venue', 'LIKE', "%$search%")
                        ->orWhere('address', 'LIKE', "%$search%");
                });
            })

            ->when($dateRange['has_range'], function ($query) use ($dateRange) {
                $query->whereHas('dates', function ($q) use ($dateRange) {
                    $q->whereBetween('date', [$dateRange['start'], $dateRange['end']]);
                });
            }, function ($query) {
                $query->whereHas('dates', function ($q) {
                    $q->whereDate('date', '>=', now()->toDateString());
                });
            });

        $eventsQuery->orderBy('created_at', $earliestFlag ? 'desc' : 'asc');
        $events = $eventsQuery->paginate($perPage);

        $eventsData = $events->isEmpty() ? collect() : $events->getCollection()->map(function ($event) {
            return $this->formatEventData($event, true);
        });

        return response()->json([
            'status'  => 'success',
            'message' => 'Bookings retrieved successfully',
            'data'    => [
                'bookings'   => $eventsData->values(),
                'pagination' => [
                    'current_page' => $events->currentPage(),
                    'per_page'     => $perPage,
                    'total'        => $events->total(),
                    'last_page'    => $events->lastPage(),
                ],
            ],
        ]);
    }

    /**
     * Optimized bookings query
     */
    private function getBookingsData($userId, $search, $bookingType, $dateRange, $perPage, $earliestFlag, $today)
    {
        return Booking::where('user_id', $userId)
            ->when($search, function ($query) use ($search) {
                $query->where(function ($q) use ($search) {
                    $q->where('tracking_number', 'LIKE', "%$search%")
                        ->orWhere('customer_name', 'LIKE', "%$search%")
                        ->orWhere('booking_type', 'LIKE', "%$search%")
                        ->orWhereHas('items', function ($q) use ($search) {
                            $q->whereHas('category', function ($q) use ($search) {
                                $q->where('name', 'LIKE', "%$search%");
                            });
                        });
                });
            })
            ->when($bookingType, fn($q) => $q->where('booking_type', $bookingType))
            ->when($dateRange['has_range'], function ($query) use ($dateRange) {
                $query->whereBetween('start_date', [$dateRange['start'], $dateRange['end']]);
            }, function ($query) use ($today) {
                $query->whereHas('items', function ($q) use ($today) {
                    $q->where(function ($subQ) use ($today) {
                        $subQ->whereNotNull('flight_reference_id')
                            ->whereDate('departure_datetime', '<=', $today)
                            ->whereDate('arrival_datetime', '>=', $today)
                            ->orWhere(function ($subQ) use ($today) {
                                $subQ->whereNull('flight_reference_id')
                                    ->whereDate('started_at', '<=', $today)
                                    ->whereDate('ended_at', '>=', $today);
                            });
                    });
                });
            })
            ->with($this->optimizedBookingRelationships($dateRange, $today))
            ->select('id', 'user_id', 'tracking_number', 'customer_name', 'customer_address', 'start_date', 'end_date', 'booking_type', 'created_at')
            ->orderBy('created_at', $earliestFlag ? 'desc' : 'asc')
            ->paginate($perPage);
    }

    /**
     * Optimized reservations query
     */
    private function getReservationsData($userId, $search, $dateRange, $perPage, $earliestFlag, $today)
    {
        return AgentRestaurantTableReservation::where('user_id', $userId)
            ->select('id', 'user_id', 'agent_id', 'dining_area_id', 'reservation_date', 'reservation_time', 'status', 'reference', 'created_at')
            ->with($this->optimizedReservationRelationships())
            ->whereNull('deleted_at')
            ->when($search, function ($query) use ($search) {
                $query->where(function ($q) use ($search) {
                    $q->where('reference', 'LIKE', "%$search%")
                        ->orWhereHas('owner', function ($q) use ($search) {
                            $q->where('first_name', 'LIKE', "%$search%")
                                ->orWhere('last_name', 'LIKE', "%$search%");
                        })
                        ->orWhereHas('diningArea', function ($q) use ($search) {
                            $q->where('dining_area_name', 'LIKE', "%$search%");
                        });
                });
            })
            ->when($dateRange['has_range'], function ($query) use ($dateRange) {
                $query->whereBetween('reservation_date', [$dateRange['start'], $dateRange['end']]);
            }, function ($query) use ($today) {
                $query->whereDate('reservation_date', '>=', $today);
            })
            ->orderBy('created_at', $earliestFlag ? 'desc' : 'asc')
            ->paginate($perPage);
    }

    /**
     * Optimized events query
     */
    private function getEventsData($userId, $search, $dateRange, $perPage, $earliestFlag, $eventStatus, $today, $request)
    {
        $userEmail = auth()->user()->email;

        $query = UserEvent::where('user_id', $userId)
            ->whereHas('dates', function ($query) {
                $query->where('date', '>', now()->format('Y-m-d'))
                    ->orWhere(function ($q) {
                        $q->where('date', '=', now()->format('Y-m-d'))
                            ->where('start_time', '>', now()->format('H:i:s'));
                    });
            })
            ->orWhereHas('guestsList', function ($query) use ($userId) {
                $query->where('user_id', $userId);
            })
            ->orWhereHas('cohost', function ($query) use ($userEmail) {
                $query->where('email', $userEmail);
            })
            ->with($this->optimizedUserEventRelationships())
            ->when($eventStatus, fn($q) => $q->where('status', $eventStatus))
            ->when($search, function ($query) use ($search) {
                $query->where(function ($q) use ($search) {
                    $q->where('title', 'LIKE', "%$search%")
                        ->orWhere('venue', 'LIKE', "%$search%")
                        ->orWhere('address', 'LIKE', "%$search%");
                });
            })
            ->when($dateRange['has_range'], function ($query) use ($dateRange) {
                $query->whereHas('dates', function ($q) use ($dateRange) {
                    $q->whereBetween('date', [$dateRange['start'], $dateRange['end']]);
                });
            }, function ($query) use ($today) {
                $query->whereHas('dates', function ($q) use ($today) {
                    $q->whereDate('date', '>=', $today);
                });
            });

        // Apply additional filters only if they exist (reduced complexity)
        $this->applyEventFilters($query, $request);

        return $query->orderBy('created_at', $earliestFlag ? 'desc' : 'asc')
            ->paginate($perPage);
    }

    /**
     * Calculate date range once to avoid repetition
     */
    private function calculateDateRange($fromDate, $toDate, $filterBy)
    {
        if (! $fromDate) {
            return ['has_range' => false];
        }

        try {
            $start = Carbon::parse($fromDate)->startOfDay();
            $end   = Carbon::parse($toDate)->endOfDay();

            if ($filterBy === 'month') {
                $start = Carbon::parse($fromDate)->startOfMonth();
                $end   = Carbon::parse($toDate)->endOfMonth();
            }

            return ['has_range' => true, 'start' => $start, 'end' => $end];
        } catch (\Exception $e) {
            Log::warning('Invalid date format', [
                'from_date' => $fromDate,
                'to_date'   => $toDate,
                'error'     => $e->getMessage(),
            ]);
            return ['has_range' => false];
        }
    }

    /**
     * Optimized relationships for bookings
     */
    private function optimizedBookingRelationships($dateRange, $today)
    {
        return [
            'items' => function ($query) use ($dateRange, $today) {
                $query->select('id', 'booking_id', 'flight_reference_id', 'departure_datetime',
                    'arrival_datetime', 'started_at', 'ended_at', 'trip_type',
                    'participants_quantity', 'category_id', 'hotel_service_id',
                    'service_id', 'agent_id')
                    ->when($dateRange['has_range'], function ($q) use ($dateRange) {
                        $start = $dateRange['start'];
                        $end   = $dateRange['end'];
                        $q->where(function ($subQ) use ($start, $end) {
                            $subQ->whereNotNull('flight_reference_id')
                                ->whereBetween('departure_datetime', [$start, $end])
                                ->orWhere(function ($subQ) use ($start, $end) {
                                    $subQ->whereNull('flight_reference_id')
                                        ->whereBetween('started_at', [$start, $end]);
                                });
                        });
                    }, function ($q) use ($today) {
                        $q->where(function ($subQ) use ($today) {
                            $subQ->whereNotNull('flight_reference_id')
                                ->whereDate('departure_datetime', '<=', $today)
                                ->whereDate('arrival_datetime', '>=', $today)
                                ->orWhere(function ($subQ) use ($today) {
                                    $subQ->whereNull('flight_reference_id')
                                        ->whereDate('started_at', '<=', $today)
                                        ->whereDate('ended_at', '>=', $today);
                                });
                        });
                    })
                    ->with([
                        'category'  => fn($q)  => $q->select('id', 'name'),
                        'hotelRoom' => fn($q) => $q->select('id', 'room_name'),
                    ]);
            },
        ];
    }

    /**
     * Optimized relationships for reservations
     */
    private function optimizedReservationRelationships()
    {
        return [
            'owner'      => fn($query)      => $query->select('id', 'first_name', 'last_name'),
            'vendor'     => fn($query)     => $query->select('id', 'first_name', 'city_id'),
            'diningArea' => fn($query) => $query->select('id', 'dining_area_name'),
        ];
    }

    /**
     * Optimized relationships for events
     */
    private function optimizedUserEventRelationships()
    {
        return [
            'dates'        => function ($query) {
                $query->select('id', 'user_event_id', 'date', 'start_time', 'end_time')
                    ->orderBy('date', 'asc')
                    ->orderBy('start_time', 'asc')
                    ->limit(1); // Only get the first date for listing
            },
            'tickets'      => fn($query)      => $query->select('id', 'user_event_id', 'name', 'price'),
            'user'         => fn($query)         => $query->select('id', 'first_name', 'last_name'),
            'userBookings' => function ($query) {
                $query->where('user_id', auth()->id())
                    ->select('id', 'user_event_id', 'payment_amount', 'status')
                    ->where('status', 'completed')
                    ->limit(1); // Only need one completed booking for price
            },
            'guestsList'   => function ($query) {
                $query->where('user_id', auth()->id())
                    ->select('id', 'event_id', 'guest_uuid', 'rsvp_status')
                    ->where('rsvp_status', 'accepted')
                    ->limit(1);
            },
            'cohost'       => fn($query)       => $query->select('id', 'user_event_id', 'email', 'uuid', 'user_id'),
        ];
    }

    /**
     * Apply event filters efficiently
     */
    private function applyEventFilters($query, Request $request)
    {
        // Payment date filters
        $paymentDateFrom = $request->input('payment_date_from');
        $paymentDateTo   = $request->input('payment_date_to');

        if ($paymentDateFrom && $paymentDateTo) {
            $query->whereHas('userBookings', function ($q) use ($paymentDateFrom, $paymentDateTo) {
                $q->whereBetween('created_at', [
                    Carbon::parse($paymentDateFrom)->startOfDay(),
                    Carbon::parse($paymentDateTo)->endOfDay(),
                ]);
            });
        }

        // Ticket type filter
        if ($ticketType = $request->input('ticket_type')) {
            $query->whereHas('tickets', function ($q) use ($ticketType) {
                $q->where('name', 'LIKE', "%$ticketType%");
            });
        }

        // Disbursement date filters
        $disbursementDateFrom = $request->input('disbursement_date_from');
        $disbursementDateTo   = $request->input('disbursement_date_to');

        if ($disbursementDateFrom && $disbursementDateTo) {
            $query->whereHas('userBookings.settlement', function ($q) use ($disbursementDateFrom, $disbursementDateTo) {
                $q->whereBetween('created_at', [
                    Carbon::parse($disbursementDateFrom)->startOfDay(),
                    Carbon::parse($disbursementDateTo)->endOfDay(),
                ]);
            });
        }
    }

    /**
     * Process bookings data efficiently
     */
    private function processBookingsData($bookings)
    {
        if ($bookings->isEmpty()) {
            return collect();
        }

        return $bookings->getCollection()->groupBy('id')->flatMap(function ($bookingGroup) {
            $booking = $bookingGroup->first();
            $items   = $booking->items;
            if ($items->isEmpty()) {
                return collect();
            }

            $categoryName = $items->first()->category->name ?? $booking->booking_type ?? 'Unknown';
            $type         = strtolower($categoryName);

            if (in_array($type, ['restaurants/lounges/clubs', 'restaurant meal pre-order', 'night life pre-order'])) {
                return collect([]);
            }

            $baseData = [
                'booking_id'      => $booking->id,
                'business_name'   => $this->vendorNameBooking($items->first(), $booking),
                'id'              => $this->generateBookingId($categoryName, $booking->id),
                'type'            => $type,
                'img_url'         => $this->formatImg($items->first(), $booking),
                'title'           => $categoryName,
                'location'        => $this->formatLocation($items->first(), $booking),
                'tracking_number' => $booking->tracking_number ?? 'N/A',
                'created_at'      => $booking->created_at,
            ];

            return $this->mapBookingTypeData($baseData, $type, $items, $booking);
        })->filter();
    }

    /**
     * Map booking type data efficiently
     */
    private function mapBookingTypeData($baseData, $type, $items, $booking)
    {
        switch ($type) {
            case 'hotels':
                $roomTypes = $items->filter(function ($item) {
                    return $item->hotelRoom && $item->hotelRoom->room_name;
                })->map(function ($item) {
                    return $item->hotelRoom->room_name;
                })->unique()->values()->toArray();

                return collect([array_merge($baseData, [
                    'room_types'     => $roomTypes,
                    'check_in_date'  => Carbon::parse($items->first()->started_at)->format('M d, Y'),
                    'check_out_date' => Carbon::parse($items->first()->ended_at)->format('M d, Y'),
                ])]);

            case 'tours and activities':
            case 'services':
            case 'travel items':
                return $items->map(function ($item) use ($baseData) {
                    return array_merge($baseData, [
                        'id'           => $this->generateBookingId($baseData['title'], $item->id),
                        'duration'     => $this->calculateDuration($item->started_at, $item->ended_at),
                        'date'         => Carbon::parse($item->started_at)->format('M d, Y'),
                        'participants' => $item->participants_quantity ?? 1,
                    ]);
                });

            case 'flights':
                return $items->map(function ($item) use ($baseData) {
                    return array_merge($baseData, [
                        'id'             => $this->generateBookingId($baseData['title'], $item->id),
                        'flight_type'    => ucfirst(str_replace('-', ' ', $item->trip_type ?? 'one-way')),
                        'travel_time'    => $this->calculateDuration($item->departure_datetime, $item->arrival_datetime),
                        'departure_date' => Carbon::parse($item->departure_datetime)->format('M d, Y'),
                        'passengers'     => $item->participants_quantity ?? 1,
                    ]);
                });

            default:
                return collect([$baseData]);
        }
    }

    /**
     * Process reservations data efficiently
     */
    private function processReservationsData($reservations)
    {
        if ($reservations->isEmpty()) {
            return collect();
        }

        return $reservations->getCollection()->map(function ($reservation) {
            $type         = 'restaurants';
            $categoryName = $reservation->diningArea->dining_area_name ?? 'Restaurant Reservation';

            return [
                'booking_id'       => $reservation->id,
                'id'               => $this->generateBookingId($categoryName, $reservation->id),
                'business_name'    => $this->vendorNameRestaurant($reservation),
                'type'             => $type,
                'img_url'          => $this->formatRestaurantImg($reservation),
                'title'            => $categoryName,
                'location'         => $this->formatLocationReservation($reservation),
                'tracking_number'  => $reservation->reference ?? 'N/A',
                'reservation_date' => Carbon::parse($reservation->reservation_date)->format('M d, Y'),
                'time'             => Carbon::parse($reservation->reservation_time)->format('h:i A'),
                'guests'           => $reservation->guests ?? 1,
                'created_at'       => $reservation->created_at,
            ];
        });
    }

    /**
     * Process events data efficiently
     */
    private function processEventsData($events, $eventsOnly)
    {
        if ($events->isEmpty()) {
            return collect();
        }

        return $events->getCollection()->map(function ($event) use ($eventsOnly) {
            return $this->formatEventData($event, $eventsOnly);
        });
    }

    /**
     * Format event data efficiently
     */
    private function formatEventData($event, $eventsOnly)
    {
        $type         = $eventsOnly ? 'event_individual' : 'events';
        $categoryName = $event->title ?? 'Event';
        $userId       = auth()->id();

        // Get price efficiently
        $price = null;
        if ($event->entry === 'ticket') {
            if ($event->relationLoaded('userBookings') && $event->userBookings->isNotEmpty()) {
                $completedBooking = $event->userBookings->where('status', 'completed')->first();
                $price            = $completedBooking ? $completedBooking->payment_amount : null;
            } else if ($event->relationLoaded('tickets') && $event->tickets->isNotEmpty()) {
                $price = $event->tickets->min('price');
            }
        }

        // Get first date efficiently
        $firstDate = $event->dates->first();
        $eventDate = $firstDate ? Carbon::parse($firstDate->date)->format('Y-m-d') : 'N/A';
        $startTime = $firstDate && $firstDate->start_time ? Carbon::parse($firstDate->start_time)->format('h:i A') : 'N/A';
        $endTime   = $firstDate && $firstDate->end_time ? Carbon::parse($firstDate->end_time)->format('h:i A') : 'N/A';

        // Get booking stats efficiently
        $userBookings      = $event->relationLoaded('userBookings') ? $event->userBookings : collect();
        $totalBookings     = $userBookings->count();
        $completedBookings = $userBookings->where('status', 'completed')->count();
        $pendingBookings   = $userBookings->where('status', 'pending')->count();
        $totalRevenue      = $userBookings->where('status', 'completed')->sum('payment_amount');
        $hasSettlement     = $userBookings->where('settlement', '!=', null)->isNotEmpty();

        // Get ticket types
        $ticketTypes = $event->relationLoaded('tickets') ? $event->tickets->pluck('name')->toArray() : [];

        // Check co-manager status efficiently
        $userEmail   = auth()->user()->email;
        $isCoManager = $event->relationLoaded('cohost') &&
        $event->cohost->contains(fn($cohost) => $cohost->email === $userEmail);

        // get guest infomation

        $eventGuest = $event->relationLoaded('guestsList') ? $event->guestsList : collect();

        return [
            'booking_id'         => $event->id,
            'id'                 => $this->generateBookingId($categoryName, $event->id),
            'business_name'      => $event->user->first_name . ' ' . $event->user->last_name,
            'type'               => $type,
            'event_id'           => $event->id,
            'img_url'            => $event->cover_image ?? 'N/A',
            'cover_image'        => $event->cover_image ?? 'N/A',
            'title'              => $categoryName,
            'location'           => $event->venue ?? $event->address ?? 'N/A',
            'tracking_number'    => $event->uuid ?? 'N/A',
            'uuid'               => $event->uuid ?? 'N/A',
            'event_date'         => $eventDate,
            'start_time'         => $startTime,
            'end_time'           => $endTime,
            'guests'             => $event->guests ?? 0,
            'entry_type'         => $event->entry ?? 'free',
            'venue'              => $event->venue ?? 'N/A',
            'address'            => $event->address ?? 'N/A',
            'description'        => $event->description ?? 'N/A',
            'owner'              => $event->user_id === $userId,
            'price'              => $price,
            'ticket_types'       => $ticketTypes,
            'total_bookings'     => $totalBookings,
            'completed_bookings' => $completedBookings,
            'pending_bookings'   => $pendingBookings,
            'total_revenue'      => $totalRevenue,
            'has_settlement'     => $hasSettlement,
            'status'             => $event->status ?? 'draft',
            'created_at'         => $event->created_at,
            'guest_uuid'         => $eventGuest->isNotEmpty() ? $eventGuest->first()->guest_uuid : null,
            'co-manager'         => $isCoManager,
            'cohost_uuid'        => $isCoManager ? $event->cohost->where('email', $userEmail)->first()->uuid : null,
        ];
    }

    /**
     * Check if user has any active bookings (fast boolean check)
     * Active bookings = currently active OR future bookings
     *
     * @param Request $request
     * @return \Illuminate\Http\JsonResponse
     */
    public function hasActiveBookings(Request $request)
    {
        $userId = auth()->id();
        $today  = Carbon::today();

        // Check for active bookings (currently active OR future)
        $hasActiveBookings = Booking::where('user_id', $userId)
            ->whereHas('items', function ($query) use ($today) {
                $query->where(function ($q) use ($today) {
                    // Currently active bookings
                    $q->where(function ($subQ) use ($today) {
                        $subQ->whereNotNull('flight_reference_id')
                            ->whereDate('departure_datetime', '<=', $today)
                            ->whereDate('arrival_datetime', '>=', $today);
                    })
                        ->orWhere(function ($subQ) use ($today) {
                            $subQ->whereNull('flight_reference_id')
                                ->whereDate('started_at', '<=', $today)
                                ->whereDate('ended_at', '>=', $today);
                        })
                    // Future bookings
                        ->orWhere(function ($subQ) use ($today) {
                            $subQ->whereNotNull('flight_reference_id')
                                ->whereDate('departure_datetime', '>', $today);
                        })
                        ->orWhere(function ($subQ) use ($today) {
                            $subQ->whereNull('flight_reference_id')
                                ->whereDate('started_at', '>', $today);
                        });
                });
            })
            ->exists();

        // Check for active restaurant reservations (future or today)
        $hasActiveReservations = AgentRestaurantTableReservation::where('user_id', $userId)
            ->whereNull('deleted_at')
            ->whereDate('reservation_date', '>=', $today)
            ->exists();

        // Check for active events (future or today)
        $hasActiveEvents = UserEvent::where('user_id', $userId)
            ->whereHas('dates', function ($query) {
                $query->where('date', '>=', now()->format('Y-m-d'))
                    ->orWhere(function ($q) {
                        $q->where('date', '=', now()->format('Y-m-d'))
                            ->where('start_time', '>', now()->format('H:i:s'));
                    });
            })
            ->orWhereHas('guestsList', function ($query) use ($userId) {
                $query->where('user_id', $userId);
            })
            ->orWhereHas('cohost', function ($query) use ($userId) {
                $query->where('email', function ($subQuery) use ($userId) {
                    $subQuery->select('email')
                        ->from('users')
                        ->where('id', $userId);
                });
            })
            ->exists();

        $hasAnyActive = $hasActiveBookings || $hasActiveReservations || $hasActiveEvents;

        return response()->json([
            'status'  => 'success',
            'message' => 'Active bookings status retrieved successfully',
            'data'    => [

                'has_active_bookings' => $hasAnyActive,
                'details'             => [
                    'bookings'     => $hasActiveBookings,
                    'reservations' => $hasActiveReservations,
                    'events'       => $hasActiveEvents,
                ],
            ],
        ]);
    }

    public function getActiveBookingsResource(Request $request)
    {
        $userId          = $request->user()->id;
        $currentDateTime = Carbon::now();

        $bookingsQuery = Booking::where('user_id', $userId)
            ->whereHas('items', function ($query) use ($currentDateTime) {
                $query->where(function ($q) use ($currentDateTime) {
                    $q->whereNotNull('flight_reference_id')
                        ->whereDate('departure_datetime', '<=', $currentDateTime)
                        ->whereDate('arrival_datetime', '>=', $currentDateTime)
                        ->orWhere(function ($q) use ($currentDateTime) {
                            $q->whereNull('flight_reference_id')
                                ->whereDate('started_at', '<=', $currentDateTime)
                                ->whereDate('ended_at', '>=', $currentDateTime);
                        });
                });
            });

        $restaurantReservationsQuery = AgentRestaurantTableReservation::where('user_id', $userId)
            ->whereNull('deleted_at')
            ->whereRaw("CONCAT(reservation_date, ' ', reservation_time) >= ?", [$currentDateTime]);

        $isHotelBooking = $bookingsQuery->clone()->whereHas('items.category', function ($q) {
            $q->where('name', 'hotels');
        })->exists();

        $totalItems = $bookingsQuery->count() + $restaurantReservationsQuery->count();

        if ($request->events_only) {

            $futureEventsCount = auth()->user()->events()
                ->whereHas('dates', function ($query) {
                    $query->where('date', '>', now()->format('Y-m-d'))
                        ->orWhere(function ($q) {
                            $q->where('date', '=', now()->format('Y-m-d'))
                                ->where('start_time', '>', now()->format('H:i:s'));
                        });
                })
                ->count();

            $futureInvitedEventsCount = auth()->user()->allInvitedEvents()
                ->whereHas('dates', function ($query) {
                    $query->where('date', '>', now()->format('Y-m-d'))
                        ->orWhere(function ($q) {
                            $q->where('date', '=', now()->format('Y-m-d'))
                                ->where('start_time', '>', now()->format('H:i:s'));
                        });
                })
                ->count();

            $totalItems = $futureEventsCount + $futureInvitedEventsCount;

        }

        return response()->json([
            'status' => 'success',
            'data'   => [
                'is_vi_enabled'         => $isHotelBooking,
                'active_booking_length' => $totalItems,
            ],
        ]);
    }

    private function generateBookingId($categoryName, $id)
    {
        $prefix = strtoupper(substr(str_replace(' ', '', $categoryName), 0, 3));
        return $prefix . '-' . str_pad($id, 5, '0', STR_PAD_LEFT);
    }

    private function formatLocation($item, $booking)
    {
        $location = null;
        if (in_array($item->category_id, [8, 10])) {
            $location = "{$item?->vendor?->vendorAccount?->city?->name}, {$item?->vendor?->vendorAccount?->state?->name}";
        }
        if (in_array($item->category_id, [1, 5])) {
            $location = $item?->service?->location;
        }
        if (in_array($item->category_id, [7])) {

            $location = $booking->destination();
            if (! $location && ($booking->city || $booking->state)) {
                $location = ($booking->city?->name ?? '') . ($booking->state ? ', ' . $booking->state->name : '');
            }
        }

        $location = $location ?: 'N/A';

        return $location;
    }

    private function formatLocationReservation($booking)
    {
        $location = "{$booking?->vendor?->vendorAccount?->city?->name}, {$booking?->vendor?->vendorAccount?->state?->name}";

        $location = $location ?: 'N/A';

        return $location;
    }

    private function calculateDuration($start, $end)
    {
        if (! $start || ! $end) {
            return 'N/A';
        }

        $startTime = Carbon::parse($start);
        $endTime   = Carbon::parse($end);
        if ($startTime->gt($endTime)) {
            return 'N/A';
        }

        $diff = $endTime->diff($startTime);

        $hours   = $diff->h + ($diff->d * 24);
        $minutes = $diff->i;

        if ($hours === 0) {
            return "{$minutes}m";
        }
        return "{$hours}h {$minutes}m";
    }

    private function calculateDurationDays($start, $end)
    {
        if (! $start || ! $end) {
            return 'N/A';
        }

        $startDate = Carbon::parse($start);
        $endDate   = Carbon::parse($end);
        $days      = abs($endDate->diffInDays($startDate));
        return $days . ' days';
    }

    public function getActiveBookingsForToday(Request $request)
    {
        ini_set('max_execution_time', 300);
        $today        = Carbon::today();
        $now          = Carbon::now();
        $userId       = $request->user()->id;
        $perPage      = $request->input('per_page', 10);
        $currentPage  = $request->input('page', 1);
        $earliestFlag = true; // Sort latest first (descending)
        $eventsOnly   = filter_var($request->input('events_only', false), FILTER_VALIDATE_BOOLEAN);

        // Fetch active categories and normalize slugs
        $categories = Category::where('status', 1)
            ->pluck('slug', 'id')
            ->map(function ($slug) {
                $slug = str_replace(['-', 'and'], ['', '&'], strtolower($slug));
                return in_array($slug, ['hotels', 'flights']) ? rtrim($slug, 's') : $slug;
            })->toArray();

        $flightCategoryId = array_search('flight', $categories);

        // Fetch bookings
        $bookings = Booking::where('user_id', $userId)
            ->select('id', 'user_id', 'start_date', 'end_date', 'tracking_status')
            ->with([
                'items' => function ($query) use ($today, $categories) {
                    $query->select('id', 'booking_id', 'category_id', 'agent_id', 'flight_reference_id', 'tracking_number', 'tracking_status', 'started_at', 'ended_at', 'departure_datetime', 'service_id', 'hotel_service_id')
                        ->whereIn('category_id', array_keys($categories))
                        ->with([
                            'service'   => function ($q) {
                                $q->select('id', 'title');
                            },
                            'hotelRoom' => function ($q) {
                                $q->select('id', 'room_name');
                            },
                            'flight'    => function ($q) {
                                $q->select('id');
                            },
                        ]);
                },
                'user'  => function ($query) {
                    $query->select('id', 'first_name', 'last_name');
                },
            ])
            ->where(function ($query) use ($today, $flightCategoryId) {
                $query->where('start_date', '<=', $today)
                    ->where('end_date', '>=', $today)
                    ->orWhereHas('items', function ($q) use ($today, $flightCategoryId) {
                        $q->where('category_id', $flightCategoryId)
                            ->whereNotNull('flight_reference_id')
                            ->whereDate('departure_datetime', $today);
                    });
            })
            ->whereNull('deleted_at')
            ->limit(50)
            ->get();

        // Fetch restaurant reservations
        $restaurantReservations = AgentRestaurantTableReservation::where('user_id', $userId)
            ->select('id', 'user_id', 'agent_id', 'dining_area_id', 'reservation_date', 'reservation_time', 'status', 'reference')
            ->with([
                'owner'      => function ($query) {
                    $query->select('id', 'first_name', 'last_name');
                },
                'vendor'     => function ($query) {
                    $query->select('id', 'first_name', 'city_id');
                },
                'diningArea' => function ($query) {
                    $query->select('id', 'dining_area_name');
                },
            ])
            ->whereDate('reservation_date', $today)
            ->whereNull('deleted_at')
            ->limit(50)
            ->get();

        // Fetch hotel service requests
        $hotelServiceRequests = AgentHotelServiceRequest::where('user_id', $userId)
            ->select('id', 'user_id', 'agent_id', 'order_id', 'request_type_category_id', 'scheduled_cleaning_date', 'scheduled_cleaning_start_time', 'tracking_status', 'reference')
            ->with([
                'order'         => function ($query) {
                    $query->select('id', 'booking_id');
                },
                'vendor'        => function ($query) {
                    $query->select('id', 'name');
                },
                'agentCategory' => function ($query) {
                    $query->select('id', 'name');
                },
            ])
            ->whereDate('scheduled_cleaning_date', $today)
            ->whereIn('tracking_status', ['new', 'in_progress', 'assigned'])
            ->whereNull('deleted_at')
            ->limit(50)
            ->get();

        // Fetch events for today
        $events = UserEvent::where(function ($query) use ($userId) {
            $query->where('user_id', $userId)
                ->orWhereHas('guestsList', function ($query) use ($userId) {
                    $query->where('user_id', $userId);
                })
                ->orWhereHas('cohost', function ($query) use ($userId) {
                    $query->where('email', function ($subQuery) use ($userId) {
                        $subQuery->select('email')
                            ->from('users')
                            ->where('id', $userId);
                    });
                });
        })
            ->with($this->UserEventRelationships())
            ->with(['guestsList' => function ($query) use ($userId) {
                $query->where('user_id', $userId)
                    ->select('id', 'event_id', 'user_id', 'guest_uuid');
            }])
            ->whereHas('dates', function ($query) use ($today) {
                $query->whereDate('date', $today);
            })
            ->limit(50)
            ->get();

        // For events_only=true, we need to ensure we have guest_uuid for all events where user is a guest
        if ($eventsOnly) {
            $events->load(['guestsList' => function ($query) use ($userId) {
                $query->where('user_id', $userId)
                    ->select('id', 'event_id', 'user_id', 'guest_uuid');
            }]);
        }

        // Debug logging for events
        $allUserEvents   = UserEvent::where('user_id', $userId)->get();
        $eventsWithDates = UserEvent::where('user_id', $userId)->whereHas('dates')->get();
        $todayEventsRaw  = UserEvent::where('user_id', $userId)
            ->whereHas('dates', function ($query) use ($today) {
                $query->whereDate('date', $today);
            })->get();

        \Log::info('Events query debug', [
            'user_id'                 => $userId,
            'today'                   => $today->toDateString(),
            'all_user_events_count'   => $allUserEvents->count(),
            'events_with_dates_count' => $eventsWithDates->count(),
            'today_events_raw_count'  => $todayEventsRaw->count(),
            'events_count'            => $events->count(),
            'events_data'             => $events->toArray(),
            'events_only'             => $eventsOnly,
            'all_user_events'         => $allUserEvents->toArray(),
        ]);

        // Build timeline collection
        $timeline = collect();

        // Process bookings
        $bookingsData = $eventsOnly ? collect() : $bookings->map(function ($booking) use ($now, $categories, $flightCategoryId) {
            $item       = $booking->items->first();
            $categoryId = $item ? $item->category_id : null;
            $isFlight   = $categoryId == $flightCategoryId;

            $location      = 'N/A';
            $business_name = 'N/A';
            $time          = '12:00 am';
            $status        = 'unknown';
            $image_url     = null;

            if ($item) {
                try {
                    $scheduledDate = $isFlight && $item->departure_datetime
                        ? Carbon::parse($item->departure_datetime)
                        : Carbon::parse($booking->start_date);
                } catch (\Exception $e) {
                    \Log::error('Failed to parse booking date', [
                        'booking_id'         => $booking->id,
                        'departure_datetime' => $item->departure_datetime ?? null,
                        'start_date'         => $booking->start_date,
                        'error'              => $e->getMessage(),
                    ]);
                    $scheduledDate = $now;
                }

                $time = $isFlight && $item->departure_datetime
                    ? Carbon::parse($item->departure_datetime)->format('h:i a')
                    : '12:00 am';
                $status = $this->getStatus($scheduledDate, $now, $booking->tracking_status);

                if (in_array($categoryId, [8, 10])) {
                    $location = ($item->vendor?->vendorAccount?->city?->name ?? '') .
                        ($item->vendor?->vendorAccount?->state?->name ? ', ' . $item->vendor->vendorAccount->state->name : '');
                } elseif (in_array($categoryId, [1, 5])) {
                    $location = $item->service?->location ?? 'N/A';
                } elseif ($categoryId == 7) {
                    $location = $booking->destination() ??
                    (($booking->city?->name ?? '') . ($booking->state ? ', ' . $booking->state->name : '')) ?? 'N/A';
                }

                $business_name = $item->vendor?->vendorAccount?->business_name ?? 'N/A';
                $image_url     = $this->formatImg($item, $booking);
            } else {
                try {
                    $scheduledDate = Carbon::parse($booking->start_date);
                } catch (\Exception $e) {
                    \Log::error('Failed to parse booking date (no items)', [
                        'booking_id' => $booking->id,
                        'start_date' => $booking->start_date,
                        'error'      => $e->getMessage(),
                    ]);
                    $scheduledDate = $now;
                }
                $status = $this->getStatus($scheduledDate, $now, $booking->tracking_status);
            }

            $type = $categoryId && isset($categories[$categoryId]) ? $categories[$categoryId] : 'order';

            return [
                'booking_id'    => $booking->id,
                'business_name' => $business_name,
                'id'            => 'SVC-' . str_pad($booking->id, 3, '0', STR_PAD_LEFT),
                'title'         => $item ? ($item->item_name ?? 'Booking #' . $booking->id) : 'Booking #' . $booking->id,
                'image_url'     => $image_url,
                'type'          => $type,
                'location'      => $location,
                'time'          => $time,
                'status'        => $status,
                'referenceId'   => $item ? ($item->tracking_number ?? null) : null,
                'created_at'    => $this->getCreatedAtTimestamp($booking),
            ];
        });

        // Process restaurant reservations
        $reservationsData = $eventsOnly ? collect() : $restaurantReservations->map(function ($reservation) use ($now) {
            try {
                $reservationDate = Carbon::parse($reservation->reservation_date)->format('Y-m-d') . ' ' . ($reservation->reservation_time ?? '00:00:00');
                $reservationDate = Carbon::parse($reservationDate);
            } catch (\Exception $e) {
                \Log::error('Failed to parse reservation date', [
                    'reservation_id'   => $reservation->id,
                    'reservation_date' => $reservation->reservation_date,
                    'reservation_time' => $reservation->reservation_time,
                    'error'            => $e->getMessage(),
                ]);
                $reservationDate = $now;
            }
            $time          = $reservation->reservation_time ? Carbon::parse($reservation->reservation_time)->format('h:i a') : '12:00 am';
            $status        = $this->getStatus($reservationDate, $now, $reservation->status);
            $business_name = $reservation->vendor?->vendorAccount?->business_name ?? 'N/A';
            $location      = $reservation->vendor && $reservation->vendor->city ? $reservation->vendor->city->name . ', Nigeria' : 'N/A';

            return [
                'booking_id'    => $reservation->id,
                'business_name' => $business_name,
                'id'            => 'SVC-' . str_pad($reservation->id + 1000, 3, '0', STR_PAD_LEFT),
                'title'         => $reservation->diningArea ? $reservation->diningArea->dining_area_name : 'Restaurant Reservation',
                'image_url'     => $this->formatRestaurantImg($reservation),
                'type'          => 'restaurant',
                'location'      => $location,
                'time'          => $time,
                'status'        => $status,
                'referenceId'   => $reservation->reference ?? null,
                'created_at'    => $this->getCreatedAtTimestamp($reservation),
            ];
        });

        // Process hotel service requests
        $hotelServiceRequestsData = $eventsOnly ? collect() : $hotelServiceRequests->map(function ($request) use ($now) {
            try {
                $scheduledDate = $request->scheduled_cleaning_date
                    ? Carbon::parse($request->scheduled_cleaning_date . ' ' . ($request->scheduled_cleaning_start_time ?? '00:00:00'))
                    : $now;
            } catch (\Exception $e) {
                \Log::error('Failed to parse service request date', [
                    'request_id'                    => $request->id,
                    'scheduled_cleaning_date'       => $request->scheduled_cleaning_date,
                    'scheduled_cleaning_start_time' => $request->scheduled_cleaning_start_time,
                    'error'                         => $e->getMessage(),
                ]);
                $scheduledDate = $now;
            }
            $time   = $request->scheduled_cleaning_start_time ? Carbon::parse($request->scheduled_cleaning_start_time)->format('h:i a') : '12:00 am';
            $status = $this->getStatus($scheduledDate, $now, $request->tracking_status);

            $booking       = $request->order?->booking;
            $location      = $booking ? ($booking->destination() ?? ($booking->city?->name . ($booking->state ? ', ' . $booking->state->name : '')) ?? 'N/A') : 'N/A';
            $business_name = $request->vendor?->vendorAccount?->business_name ?? 'N/A';
            $type          = $request->request_type_category_id && $request->agentCategory ? ($request->agentCategory->name === 'Laundry' ? 'laundry' : ($request->agentCategory->name === 'Housekeeping' ? 'housekeeping' : 'order')) : 'order';
            $img_url       = $request->vendor?->vendorAccount?->business_logo_image ?? null;

            return [
                'booking_id'    => $request->id,
                'business_name' => $business_name,
                'id'            => 'SVC-' . str_pad($request->id + 2000, 3, '0', STR_PAD_LEFT),
                'title'         => $request->agentCategory ? $request->agentCategory->name : 'Service Request',
                'type'          => $type,
                'image_url'     => $img_url,
                'location'      => $location,
                'time'          => $time,
                'status'        => $status,
                'referenceId'   => $request->reference ?? null,
                'created_at'    => $this->getCreatedAtTimestamp($request),
            ];
        });

        // Process events
        $eventsData = $events->map(function ($event) use ($now, $eventsOnly, $userId) {
            $type         = $eventsOnly ? 'event_individual' : 'events';
            $categoryName = $event->title ?? 'Event';

            // Get the first date for this event (since we're filtering by today)
            $eventDate = $event->dates->first();
            $startTime = $eventDate ? $eventDate->start_time : null;
            $endTime   = $eventDate ? $eventDate->end_time : null;

            // Get guest_uuid when events_only=true and user is a guest
            $guestUuid = null;
            if ($eventsOnly && $event->relationLoaded('guestsList') && $event->guestsList->isNotEmpty()) {
                $guestUuid = $event->guestsList->first()->guest_uuid;
            }

            // Debug logging for guest_uuid
            \Log::info('Event processing debug', [
                'event_id'          => $event->id,
                'events_only'       => $eventsOnly,
                'user_id'           => $userId,
                'event_user_id'     => $event->user_id,
                'is_owner'          => $event->user_id === $userId,
                'guestsList_loaded' => $event->relationLoaded('guestsList'),
                'guestsList_count'  => $event->guestsList->count(),
                'guestsList_data'   => $event->guestsList->toArray(),
                'guest_uuid'        => $guestUuid,
            ]);

            $eventData = [
                'booking_id'    => $event->id,
                'business_name' => $event->user->first_name . ' ' . $event->user->last_name,
                'id'            => 'SVC-' . str_pad($event->id + 3000, 3, '0', STR_PAD_LEFT),
                'title'         => $categoryName,
                'event_id'      => $event->id,
                'event_uuid'    => $event->uuid,
                'owner'         => $event->user_id === auth()->id(),
                'co-manager'    => $event->relationLoaded('cohost') &&
                $event->cohost->contains(fn($cohost) => $cohost->email === auth()->user()->email),
                'image_url'     => $event->cover_image ?? 'N/A',
                'type'          => $type,
                'location'      => $event->venue ?? $event->address ?? 'N/A',
                'time'          => $startTime ? Carbon::parse($startTime)->format('h:i a') : '12:00 am',
                'status'        => 'Ongoing',
                'referenceId'   => $event->uuid ?? null,
                'created_at'    => $this->getCreatedAtTimestamp($event),
            ];

            // Add guest_uuid when events_only=true (can be null)
            if ($eventsOnly) {
                $eventData['guest_uuid'] = $guestUuid;
            }

            return $eventData;
        });

        // Merge and sort the collections
        \Log::info('Timeline before sorting', [
            'bookings'             => $bookingsData->toArray(),
            'reservations'         => $reservationsData->toArray(),
            'hotelServiceRequests' => $hotelServiceRequestsData->toArray(),
            'events'               => $eventsData->toArray(),
        ]);
        $mergedData = $bookingsData->merge($reservationsData)->merge($hotelServiceRequestsData)->merge($eventsData)
            ->sortBy([
                ['created_at', $earliestFlag ? 'desc' : 'asc'],
            ]);
        \Log::info('Timeline after sorting', $mergedData->toArray());

        // Paginate the timeline
        $total     = $mergedData->count();
        $timeline  = $mergedData->slice(($currentPage - 1) * $perPage, $perPage)->values();
        $paginator = new LengthAwarePaginator($timeline, $total, $perPage, $currentPage, [
            'path'  => $request->url(),
            'query' => $request->query(),
        ]);

        return response()->json([
            'status'  => 'success',
            'message' => 'Today\'s timeline retrieved successfully',
            'data'    => [
                'todays_timeline' => $timeline,
                'pagination'      => [
                    'current_page' => $paginator->currentPage(),
                    'per_page'     => $paginator->perPage(),
                    'total'        => $paginator->total(),
                    'last_page'    => $paginator->lastPage(),
                ],
            ],
        ]);
    }

    private function getCreatedAtTimestamp($record): int
    {
        try {
            return Carbon::parse($record->created_at)->timestamp;
        } catch (\Exception $e) {
            \Log::error('Failed to parse created_at', [
                'record_id'  => $record->id,
                'created_at' => $record->created_at,
                'error'      => $e->getMessage(),
            ]);
            return Carbon::now()->timestamp; // Fallback
        }
    }

    private function getStatus($scheduledDate, $now, $trackingStatus): string
    {
        if (is_string($scheduledDate)) {
            try {
                $scheduledDate = Carbon::parse($scheduledDate);
            } catch (\Exception $e) {
                \Log::error('Failed to parse scheduledDate in getStatus', [
                    'scheduledDate' => $scheduledDate,
                    'error'         => $e->getMessage(),
                ]);
                $scheduledDate = $now;
            }
        }

        if (in_array($trackingStatus, ['pending', 'unconfirmed', 'new'])) {
            return 'Pending';
        }

        return 'Ongoing';
    }

    private function vendorNameRestaurant($booking)
    {
        $business_name = "{$booking?->vendor?->vendorAccount?->business_name}";
        $business_name = $business_name ?: 'N/A';

        return $business_name;

    }
    private function formatImg($item, $booking)
    {

        $image = null;
        if (in_array($item->category_id, [8, 10])) {
            $image = $item->category_id == 8 ? $item?->vendor?->hotelGallery()->where('is_main', 1)->first() : $item?->vendor?->restaurantGallery()->where('is_main', 1)->first();
        }
        if (in_array($item->category_id, [1, 5])) {
            $image = $item?->service?->cover_image;
        }
        if (in_array($item->category_id, [7])) {

        }
        if (in_array($item->category_id, [11])) {
            $image = $item?->vendor?->vendorAccount?->business_logo_image;
        }
        $image = $image ?: 'N/A';

        return $image;
    }

    private function vendorNameBooking($item, $booking)
    {
        $business_name = "{$item?->vendor?->vendorAccount?->business_name}";
        $business_name = $business_name ?: 'N/A';

        return $business_name;

    }
    private function formatRestaurantImg($booking)
    {
        $image = null;
        $image = $booking?->vendor?->restaurantGallery()->where('is_main', 1)->first();

        $image = $image ?: 'N/A';

        return $image;
    }

    /**
     * Debug method to test events query
     */
    public function debugEvents(Request $request)
    {
        $userId = auth()->id();

        // Test basic query
        $allEvents = UserEvent::where('user_id', $userId)->get();

        // Test with relationships
        $eventsWithRelations = UserEvent::where('user_id', $userId)
            ->with($this->UserEventRelationships())
            ->get();

        // Test pagination
        $eventsPaginated = UserEvent::where('user_id', $userId)
            ->with($this->UserEventRelationships())
            ->paginate(10);

        return response()->json([
            'status' => 'success',
            'debug'  => [
                'user_id'                     => $userId,
                'total_events_count'          => $allEvents->count(),
                'all_events'                  => $allEvents->toArray(),
                'events_with_relations_count' => $eventsWithRelations->count(),
                'events_with_relations'       => $eventsWithRelations->toArray(),
                'paginated_events_count'      => $eventsPaginated->count(),
                'paginated_events_total'      => $eventsPaginated->total(),
                'paginated_events'            => $eventsPaginated->items(),
            ],
        ]);
    }

    private function UserEventRelationships()
    {
        return [
            'type'           => function ($query) {
                $query->select('id', 'name');
            },
            'dates'          => function ($query) {
                $query->select('id', 'user_event_id', 'date', 'start_time', 'end_time', 'timezone_id');
            },
            'dates.timezone' => function ($query) {
                $query->select('id', 'name', 'identifier', 'offset', 'offset_hours', 'utc_offset', 'is_dst');
            },
            'tickets'        => function ($query) {
                $query->select('id', 'user_event_id', 'name', 'description', 'price', 'currency', 'quantity');
            },
            'imageGallery'   => function ($query) {
                $query->select('id', 'user_event_id', 'image_url');
            },
            'user'           => function ($query) {
                $query->select('id', 'first_name', 'last_name', 'profile_photo', 'username')
                    ->with(['city' => function ($q) {
                        $q->select('id', 'name');
                    }]);
            },
            'userBookings'   => function ($query) {
                $query->where('user_id', auth()->id())
                    ->select('id', 'user_event_id', 'user_id', 'payment_amount', 'status', 'created_at')
                    ->with(['settlement' => function ($q) {
                        $q->select('id', 'user_booking_id', 'amount', 'created_at');
                    }]);
            },
            'cohost'         => function ($query) {
                $query->select('id', 'user_event_id', 'email', 'status', 'has_decided');
            },
        ];
    }

}
