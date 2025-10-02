<?php

namespace App\Models;

use App\Observers\Observable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Support\Carbon;

class BookingItem extends Model
{
    use HasFactory, SoftDeletes, Observable;

    protected $table = 'agent_booking_items';
    protected $guarded = [];
    protected $casts = [
        "price_details" => "object",
        "additional_price_details" => "object",
        "guests" => "array",
    ];
    protected $appends = [
        "earnings",
    ];
    /**
     * Appends
     * */
    public function getEarningsAttribute(): float
    {
        return $this->total_amount - $this->commission_amount;
    }

  public function getItemNameAttribute(): string
{
    if ($this->service_id && $this->service && !is_null($this->service->title)) {
        return $this->service->title;
    }
    if ($this->hotel_service_id && $this->hotelRoom && !is_null($this->hotelRoom->room_name)) {
        return $this->hotelRoom->room_name;
    }
    if ($this->flight_reference_id) {
        $airportName = $this->getAirportName($this->departure, $this->arrival);
        if ($airportName !== null) {
            return $airportName;
        }
    }
    return $this->tracking_number ?? 'Unnamed Booking Item';
}
    private function getAirportName($code1, $code2 = null)
    {
        $airport = Airport::where("airport_code", $code1)->first()?->airport_name;

        if ($code2) return $airport. " - ". Airport::where("airport_code", $code2)->first()?->airport_name;

        return $airport;
    }
    public function getScheduledDateAttribute(): string
    {
        //logic for those that does not use started_at
        if ($this->flight_reference_id) return $this->departure_datetime;

        return $this->started_at;
    }


    public function booking(): BelongsTo
    {
        return $this->belongsTo(Booking::class, 'booking_id');
    }

    /**
     * Scopes
     **/
    public function scopeIsConfirmed($query)
    {
        $query->where("tracking_status", "confirmed");
    }

    /**
     * Scopes
     **/
    public function scopeIsPaid($query)
    {
        $query->whereRelation('booking.transactions.payment', 'status', 'successful');
    }

    public function scopeIsPending($query)
    {
        $query->where("tracking_status", "pending");
    }
    public function scopeFromLastMonth($builder): void
    {
        $builder->whereBetween("created_at", [now()->subMonth()->startOfMonth(), now()->subMonth()->endOfMonth()]);
    }

    public function scopeCurrentMonth($builder): void
    {
        $builder->whereBetween("created_at", [now()->startOfMonth(), now()->endOfMonth()]);
    }

    public function scopeCurrentYear($builder): void
    {
        $year = Carbon::now()->year;
        $start = Carbon::createFromDate($year, 1, 1)->startOfMonth();
        $end = Carbon::createFromDate($year, 12, 1)->endOfMonth();
        $builder->whereBetween("created_at", [$start, $end]);
    }
    /**
     * Define service relationship.
     */
    public function service(): BelongsTo
    {
        return $this->belongsTo(Service::class, 'service_id');
    }

    /**
     * Define invoice relationship.
     */
    public function invoice(): BelongsTo
    {
        return $this->belongsTo(Invoice::class, 'invoice_id');
    }

    /**
     * Define vendor relationship.
     */
    public function vendor(): BelongsTo
    {
        return $this->belongsTo(User::class, 'agent_id');
    }

    /**
     * Define settlement relationship.
     */
    public function settlements(): HasMany
    {
        return $this->hasMany(AgentSettlement::class,'booking_item_id');
    }

    /**
     * Define category relationship.
     */
    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class, 'category_id');
    }

    /**
     * Define settlement relationship.
     */
    public function participants(): HasMany
    {
        return $this->hasMany(BookingParticipant::class,'booking_item_id');
    }

    public function markup()
    {
        return $this->belongsTo(Markup::class);
    }

    public function flight(): BelongsTo
    {
        return $this->belongsTo(FlightSearchResults::class, 'flight_reference_id');
    }

    public function hotelRoom(): BelongsTo
    {
        return $this->belongsTo(AgentHotelRoom::class, 'hotel_service_id');
    }

    /**
     * Define item relationship.
     */
    public function promotion(): BelongsTo
    {
        return $this->belongsTo(Promotion::class, 'promotion_id');
    }

    public function country(){
        return $this->belongsTo(Country::class, 'country_id');
    }

    public function itinerary()
    {
        return $this->belongsTo(TripItenaries::class, 'trip_itinerary_id', 'id');
    }

    public function modificationHistories()
    {
        return $this->hasMany(BookingModificationHistory::class, 'booking_item_id');
    }

    public function city()
{
    return $this->belongsTo(City::class, 'city_id');
}

public function state()
{
    return $this->belongsTo(State::class, 'state_id');
}


}
