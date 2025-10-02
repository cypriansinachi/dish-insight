import datetime
from typing import Any, Dict, List, Optional

from db_connection import fetch_all, fetch_one


def _today_date_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


async def has_active_bookings(user_id: int) -> Dict[str, bool]:
    """
    Fast boolean checks inspired by BookingController::hasActiveBookings.
    Active if any of: bookings with items currently active or in future,
    restaurant reservations today/future, or user events today/future.
    """

    today = _today_date_str()

    # Active bookings (by items) — current or future
    sql_active_bookings = (
        """
        SELECT 1
        FROM agent_bookings b
        JOIN agent_booking_items i ON i.booking_id = b.id
        WHERE b.user_id = %s
          AND (
                (
                  i.flight_reference_id IS NOT NULL
                  AND DATE(i.departure_datetime) <= %s
                  AND DATE(i.arrival_datetime) >= %s
                )
             OR (
                  i.flight_reference_id IS NULL
                  AND DATE(i.started_at) <= %s
                  AND DATE(i.ended_at) >= %s
                )
             OR (
                  i.flight_reference_id IS NOT NULL AND DATE(i.departure_datetime) > %s
                )
             OR (
                  i.flight_reference_id IS NULL AND DATE(i.started_at) > %s
                )
          )
        LIMIT 1
        """
    )
    has_bookings = bool(
        await fetch_one(sql_active_bookings, (user_id, today, today, today, today, today, today))
    )

    # Active restaurant reservations (today or future)
    sql_active_res = (
        """
        SELECT 1
        FROM restaurant_table_reservations r
        WHERE r.user_id = %s
          AND r.deleted_at IS NULL
          AND DATE(r.reservation_date) >= %s
        LIMIT 1
        """
    )
    has_res = bool(await fetch_one(sql_active_res, (user_id, today)))

    # Active events: owned or cohost — today/future
    sql_user_email = "SELECT email FROM users WHERE id = %s LIMIT 1"
    user_row = await fetch_one(sql_user_email, (user_id,))
    user_email = user_row["email"] if user_row else None

    sql_active_events_owned = (
        """
        SELECT 1
        FROM user_events e
        WHERE e.user_id = %s
          AND EXISTS (
            SELECT 1 FROM user_event_dates d
            WHERE d.user_event_id = e.id
              AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
          )
        LIMIT 1
        """
    )
    owned = bool(await fetch_one(sql_active_events_owned, (user_id, today, today)))

    cohost = False
    if user_email:
        sql_active_events_cohost = (
            """
            SELECT 1
            FROM user_events e
            WHERE EXISTS (
                SELECT 1 FROM user_event_cohosts c
                WHERE c.user_event_id = e.id AND c.email = %s
            )
              AND EXISTS (
                SELECT 1 FROM user_event_dates d
                WHERE d.user_event_id = e.id
                  AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
              )
            LIMIT 1
            """
        )
        cohost = bool(await fetch_one(sql_active_events_cohost, (user_email, today, today)))

    has_events = owned or cohost

    return {
        "bookings": has_bookings,
        "reservations": has_res,
        "events": has_events,
    }


async def list_active_bookings(
    user_id: int,
    per_page: int = 10,
    page: int = 1,
) -> Dict[str, Any]:
    """
    Fetch active items (bookings, restaurant reservations, and events) similar to processActiveBookings.
    For simplicity, we return a unified flat list with minimal fields needed by the active center.
    """

    today = _today_date_str()
    offset = max(0, (page - 1) * per_page)

    # Active bookings (basic fields)
    sql_bookings = (
        """
        SELECT b.id AS booking_id,
               b.tracking_number,
               b.created_at,
               i.id AS item_id,
               i.category_id,
               i.flight_reference_id,
               i.departure_datetime,
               i.arrival_datetime,
               i.started_at,
               i.ended_at
        FROM agent_bookings b
        JOIN agent_booking_items i ON i.booking_id = b.id
        WHERE b.user_id = %s
          AND (
                (
                  i.flight_reference_id IS NOT NULL
                  AND DATE(i.departure_datetime) <= %s
                  AND DATE(i.arrival_datetime) >= %s
                )
             OR (
                  i.flight_reference_id IS NULL
                  AND DATE(i.started_at) <= %s
                  AND DATE(i.ended_at) >= %s
                )
             OR (
                  i.flight_reference_id IS NOT NULL AND DATE(i.departure_datetime) > %s
                )
             OR (
                  i.flight_reference_id IS NULL AND DATE(i.started_at) > %s
                )
          )
        ORDER BY b.created_at DESC
        LIMIT %s OFFSET %s
        """
    )
    bookings = await fetch_all(
        sql_bookings, (user_id, today, today, today, today, today, today, per_page, offset)
    )

    # Restaurant reservations (future or today)
    sql_reservations = (
        """
        SELECT r.id AS reservation_id,
               r.reference,
               r.reservation_date,
               r.reservation_time,
               r.created_at
        FROM restaurant_table_reservations r
        WHERE r.user_id = %s
          AND r.deleted_at IS NULL
          AND DATE(r.reservation_date) >= %s
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
        """
    )
    reservations = await fetch_all(sql_reservations, (user_id, today, per_page, offset))

    # Events (owned, invited, cohost) — today/future
    sql_user_email = "SELECT email FROM users WHERE id = %s LIMIT 1"
    user_row = await fetch_one(sql_user_email, (user_id,))
    user_email = user_row["email"] if user_row else None

    sql_events_owned = (
        """
        SELECT e.id AS event_id, e.title, e.uuid, e.cover_image, e.created_at
        FROM user_events e
        WHERE e.user_id = %s
          AND EXISTS (
            SELECT 1 FROM user_event_dates d
            WHERE d.user_event_id = e.id
              AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
          )
        ORDER BY e.created_at DESC
        LIMIT %s OFFSET %s
        """
    )
    events_owned_result = await fetch_all(sql_events_owned, (user_id, today, today, per_page, offset))
    if events_owned_result:
        events_owned: List[Dict[str, Any]] = list(events_owned_result)
    else:
        events_owned: List[Dict[str, Any]] = []

    events_cohost: List[Dict[str, Any]] = []
    if user_email:
        sql_events_cohost = (
            """
            SELECT e.id AS event_id, e.title, e.uuid, e.cover_image, e.created_at
            FROM user_events e
            WHERE EXISTS (
                SELECT 1 FROM user_event_cohosts c
                WHERE c.user_event_id = e.id AND c.email = %s
            )
              AND EXISTS (
                SELECT 1 FROM user_event_dates d
                WHERE d.user_event_id = e.id
                  AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
              )
            ORDER BY e.created_at DESC
            LIMIT %s OFFSET %s
            """
        )
        events_cohost_result = await fetch_all(sql_events_cohost, (user_email, today, today, per_page, offset))
        if events_cohost_result:
            events_cohost = list(events_cohost_result)
        else:
            events_cohost = []

    # Normalize to unified list
    data: List[Dict[str, Any]] = []

    for b in bookings:
        data.append(
            {
                "kind": "booking",
                "booking_id": b["booking_id"],
                "tracking_number": b.get("tracking_number"),
                "created_at": b.get("created_at"),
                "item_id": b.get("item_id"),
                "category_id": b.get("category_id"),
            }
        )

    for r in reservations:
        data.append(
            {
                "kind": "reservation",
                "reservation_id": r["reservation_id"],
                "reference": r.get("reference"),
                "reservation_date": r.get("reservation_date"),
                "reservation_time": r.get("reservation_time"),
                "created_at": r.get("created_at"),
            }
        )

    for e in events_owned + events_cohost:
        data.append(
            {
                "kind": "event",
                "event_id": e["event_id"],
                "title": e.get("title"),
                "uuid": e.get("uuid"),
                "cover_image": e.get("cover_image"),
                "created_at": e.get("created_at"),
            }
        )

    # Simple pagination metadata (not perfect cross-entity but adequate)
    return {
        "items": data,
        "pagination": {"per_page": per_page, "page": page, "count": len(data)},
    }


