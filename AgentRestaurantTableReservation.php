<?php

namespace App\Models;

use App\Observers\ReservationObserver;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Notifications\Notifiable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Database\Eloquent\Attributes\ObservedBy;
use Illuminate\Database\Eloquent\SoftDeletes;

#[ObservedBy([ReservationObserver::class])]
class AgentRestaurantTableReservation extends Model
{
    use Notifiable;

    use HasFactory;

    use SoftDeletes;

    protected $table = 'restaurant_table_reservations';

    protected $guarded = [];

    protected $casts = [
        'guest_information' => 'json',
        'reservation_date' => 'date',
    ];

    public function order(): HasOne
    {
        return $this->hasOne(Order::class, 'reservation_id');
    }

    public function getPaidOrderAttribute()
    {
        $order = $this->order()->first();

        if ($order && $order->isPaid()) {
            return $order;
        }

        return null;
    }

    public function vendor(): BelongsTo
    {
        return $this->belongsTo(User::class, 'agent_id');
    }

    public function owner(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function diningArea()
    {
        return $this->belongsTo(AgentRestaurantDiningArea::class, 'dining_area_id')->select('id', 'dining_area_name', 'description', 'dining_area_images', 'dining_area_tables');
    }

    public function postReviewSuggestionNotificationTrackers()
    {
        return $this->hasMany(PostReviewSuggestionNotificationTracker::class, 'reservation_id');
    }

    public function post(): BelongsTo
    {
        return $this->belongsTo(Post::class, 'post_id');
    }

    public function bookingRequest(): BelongsTo
    {
        return $this->belongsTo(BookingRequest::class, 'booking_request_id');
    }
}
