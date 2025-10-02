<?php

namespace App\Models;

use App\Models\Social\Post;
use App\Observers\Observable;
use Carbon\Carbon;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Database\Eloquent\Casts\Attribute;

class Booking extends Model
{
    use HasFactory, SoftDeletes, Observable;

    protected $table = 'agent_bookings';
    protected $guarded = [];
    protected $hidden = ["commission_amount"];


    public function isPaid(): bool
    {
        return (bool) $this->transactions()->whereRelation('payment', 'status', 'successful')->first();
    }

    public function item(): HasOne
    {
        return $this->hasOne(BookingItem::class, 'booking_id', );
    }

    public function user()
    {
        return $this->belongsTo(User::class)->select('id', 'first_name', 'last_name', 'email', 'phone_number');
    }

    /**
     * Define transactions relationship.
     */
    public function transactions(): HasMany
    {
        return $this->hasMany(AgentTransaction::class,'booking_id')->latest();
    }

    /**
     * Define settlements relationship.
     */
    public function settlements(): HasMany
    {
        return $this->hasMany(AgentSettlement::class,'booking_id')->latest();
    }

    public function items(): HasMany
    {
        return $this->hasMany(BookingItem::class, 'booking_id', );
    }

    public function flightItems(): HasOne
    {
        return $this->hasOne(BookingItem::class, 'booking_id', );
    }

    function agencyName()
    {
        return $this->item?->flight?->vendor?->vendorAccount?->business_name;
    }

    function destination(){
        $flightInfos = $this->item?->flight?->flightInfo;
        if ($flightInfos->isEmpty()) {
            return null;
        }

        $lastFlightInfo = $flightInfos->last();
        $airportCode = last(explode(',', $lastFlightInfo->arrival_location_code));

        $airport = Airport::where('airport_code', $airportCode)->first();
        return $airport
            ? "{$airport->airport_city}, {$airport->airport_country}"
            : "Unknown, Unknown Country";
    }

    function infoAirlineNames() {
        $flightInfos = $this->item?->flight?->flightInfo;
        if ($flightInfos->isEmpty()) {
            return [];
        }

        $airlineCodes = [];
        foreach ($flightInfos as $info) {
            $airlineCodes = array_merge($airlineCodes, explode(",", $info->operating_airline_code));
        }

        return Airline::whereIn('airline_code', $airlineCodes)
            ->pluck('airline_name')
            ->toArray();
    }

    function agencyImage()
    {
        return $this->item?->flight?->vendor?->vendorAccount?->business_logo_image;
    }

    public function plannedTrip(): BelongsTo
    {
        return $this->belongsTo(PlannedTrip::class, 'planned_trip_id');
    }

    public function post(): BelongsTo
    {
        return $this->belongsTo(Post::class, 'post_id');
    }

    function scopeIsPaid($query)
    {
        return $query->whereHas('transactions', function ($q) {
            $q->whereHas('payment', function ($q) {
                $q->where('status', 'successful');
            });
        });
    }

    protected function hasActiveHotelService(): Attribute{
        return Attribute::make(
            get: fn() => $this->item && $this->item->vendor && $this->item->vendor->agentHotelServiceRequestTypeCategories
                ? $this->item->vendor->agentHotelServiceRequestTypeCategories->where('is_active', 1)->exists()
                : false
        );
    }

    protected function canBeModified(): Attribute{
        return Attribute::make(
            get: function () {
                $startDate = Carbon::parse($this->start_date);
                $modificationDuration = $this->modification_duration;
                $modificationPeriod = $this->modification_period;
                if (!$modificationDuration || !$modificationPeriod) {
                    return false;
                }

                $modificationDeadline = match ($modificationPeriod) {
                    'months' => $startDate->copy()->subMonths($modificationDuration),
                    'weeks' => $startDate->copy()->subWeeks($modificationDuration),
                    'days' => $startDate->copy()->subDays($modificationDuration),
                    'hours' => $startDate->copy()->subHours($modificationDuration),
                    default => null
                };

                if (!$modificationDeadline) {
                    return false;
                }

                return now()->lt($modificationDeadline);
            }
        );
    }

    protected function canBeCancelled(): Attribute
    {
        return Attribute::make(
            get: function () {
                $startDate = Carbon::parse($this->start_date);
                $cancellationDuration = $this->cancellation_duration;
                $cancellationPeriod = $this->cancellation_period;
                if (!$cancellationDuration || !$cancellationPeriod) {
                    return false;
                }

                $cancellationDeadline = match ($cancellationPeriod) {
                    'months' => $startDate->copy()->subMonths($cancellationDuration),
                    'weeks' => $startDate->copy()->subWeeks($cancellationDuration),
                    'days' => $startDate->copy()->subDays($cancellationDuration),
                    'hours' => $startDate->copy()->subHours($cancellationDuration),
                    default => null
                };

                if (!$cancellationDeadline) {
                    return false;
                }

                return now()->lt($cancellationDeadline);
            }
        );
    }

     public function latestModificationRequest(): HasOne
    {
        return $this->hasOne(BookingModificationRequest::class, 'booking_id')->where('type', 'modification')->where('status', 'pending')->latest();
    }
    public function latestFullModificationRequest(): HasOne
    {
        return $this->hasOne(BookingModificationRequest::class, 'booking_id')->where('type', 'modification')->where('status', 'pending')->where('hotel_modification_type', 'full_modification')->latest();
    }
    public function latestExtensionRequest(): HasOne
    {
        return $this->hasOne(BookingModificationRequest::class, 'booking_id')->where('type', 'modification')->where('status', 'pending')->where('hotel_modification_type', 'booking_extension')->latest();
    }
    public function latestAdditionRequest(): HasOne
    {
        return $this->hasOne(BookingModificationRequest::class, 'booking_id')->where('type', 'modification')->where('status', 'pending')->where('hotel_modification_type', 'booking_addition')->latest();
    }
    public function latestGuestAdditionRequest(): HasOne
    {
        return $this->hasOne(BookingModificationRequest::class, 'booking_id')->where('type', 'modification')->where('status', 'pending')->where('hotel_modification_type', 'booking_addition_guest')->latest();
    }

}
