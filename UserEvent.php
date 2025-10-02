<?php
namespace App\Models\Social\Events;

use App\Models\User;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Support\Str;
use App\Models\UserBooking;
use App\Models\UserTransaction;

class UserEvent extends Model
{
    use SoftDeletes;
    protected $table = 'user_events';

    protected $fillable = [
        'uuid',
        'title',
        'user_id',
        'type_id',
        'event_date',
        'start_time',
        'end_time',
        'venue',
        'address',
        'description',
        'guests',
        'entry',
        'status',
        'cover_image',
        'organiser_name',
        'longitude',
        'latitude'
    ];

    protected $hidden = [
        'event_date',
        'start_time',
        'end_time',

    ];
    protected $casts = [
        'event_date' => 'datetime',
        'start_time' => 'datetime',
        'end_time'   => 'datetime',
        'guests'     => 'integer',
    ];
    protected $appends = ['price'];
    protected static function boot()
    {
        parent::boot();

        static::creating(function ($model) {
            if (empty($model->uuid)) {
                $model->uuid = Str::uuid()->toString();
            }
        });
    }

    public function user()
    {
        return $this->belongsTo(User::class);
    }

    public function type()
    {
        return $this->belongsTo(UserEventType::class, 'type_id');
    }
    public function tickets()
    {
        return $this->hasMany(UserEventTicket::class, 'user_event_id');
    }
    public function imageGallery()
    {
        return $this->hasMany(UserEventImageGallery::class, 'user_event_id');
    }
    public function form()
    {
        return $this->hasOne(UserEventForm::class, 'user_event_id');
    }

    public function cohost()
    {

        return $this->hasMany(UserEventCohost::class);
    }

    public function getPriceAttribute()
    {
        if ($this->entry === 'free') {
            return 'free';
        }

        if ($this->entry === 'ticket' && $this->relationLoaded('tickets')) {
            $tickets = $this->tickets;

            if ($tickets->isEmpty()) {
                return 'No tickets available';
            }

            $minPrice = $tickets->min('price');
            $maxPrice = $tickets->max('price');

            if ($minPrice === $maxPrice) {
                return $this->formatPrice($minPrice, $tickets->first()->currency);
            }

            return $this->formatPrice($minPrice, $tickets->first()->currency) . ' - ' .
            $this->formatPrice($maxPrice, $tickets->first()->currency);
        }

        return null;
    }

    protected function formatPrice($price, $currency)
    {

        $formats = [
            'USD' => '$%.2f',
            'EUR' => '€%.2f',
            'NGN' => '₦%.2f',

        ];

        $format = $formats[$currency] ?? '%.2f %s';

        if (strpos($format, '%s') !== false) {
            return sprintf($format, $price, $currency);
        }

        return sprintf($format, $price);
    }

    public function guestsList()
    {
        return $this->hasMany(EventGuestList::class, 'event_id', 'id');
    }

    public function dates()
    {
        return $this->hasMany(UserEventDate::class);
    }

    public function emails(){
        return $this->hasMany(UserEventEmail::class);
    }

    public function userBookings()
    {
        return $this->hasMany(UserBooking::class, 'user_event_id');
    }

    public function userTransactions()
    {
        return $this->hasMany(UserTransaction::class, 'user_event_id');
    }
    
}
