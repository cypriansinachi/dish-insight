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
    Fetch active bookings matching the PHP implementation structure.
    Returns detailed booking information with business names, types, images, etc.
    """

    today = _today_date_str()
    offset = max(0, (page - 1) * per_page)

    # Get user email for cohost events
    sql_user_email = "SELECT email FROM users WHERE id = %s LIMIT 1"
    user_row = await fetch_one(sql_user_email, (user_id,))
    user_email = user_row["email"] if user_row else None

    # Active bookings using only confirmed tables from PHP models
    # Only include bookings with items currently active or in future
    sql_bookings = (
        """
        SELECT DISTINCT
            b.id AS booking_id,
            b.tracking_number,
            b.created_at,
            'N/A' AS business_name,
            'unknown' AS type,
            'N/A' AS img_url,
            'Service' AS title,
            'N/A' AS location,
            b.id AS booking_identifier,
            CONCAT('BOK-', LPAD(b.id, 5, '0')) AS id
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
    bookings_result = await fetch_all(sql_bookings, (user_id, today, today, today, today, today, today, per_page, offset))
    if bookings_result:
        bookings: List[Dict[str, Any]] = list(bookings_result)
    else:
        bookings: List[Dict[str, Any]] = []

    # Events (owned) — using ONLY exact columns from PHP model
    # Only include events that are active (today or future)
    sql_events_owned = (
        """
        SELECT 
            e.id AS booking_id,
            e.id AS event_id,
            CONCAT('EVE-', LPAD(e.id, 5, '0')) AS id,
            CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, '')) AS business_name,
            'events' AS type,
            COALESCE(e.cover_image, 'N/A') AS img_url,
            COALESCE(e.title, 'Event') AS title,
            COALESCE(e.venue, 'N/A') AS location,
            '' AS tracking_number,
            COALESCE(e.uuid, '') AS uuid,
            COALESCE(e.event_date, 'N/A') AS event_date,
            COALESCE(e.start_time, 'N/A') AS start_time,
            COALESCE(e.end_time, 'N/A') AS end_time,
            COALESCE(e.guests, 0) AS guests,
            COALESCE(e.entry, 'free') AS entry_type,
            COALESCE(e.venue, 'N/A') AS venue,
            COALESCE(e.address, 'N/A') AS address,
            COALESCE(e.description, 'N/A') AS description,
            CASE WHEN e.user_id = %s THEN true ELSE false END AS owner,
            CASE WHEN e.entry = 'free' THEN null ELSE 'price' END AS price,
            '[]' AS ticket_types,
            0 AS total_bookings,
            0 AS completed_bookings,
            0 AS pending_bookings,
            0 AS total_revenue,
            false AS has_settlement,
            COALESCE(e.status, 'draft') AS status,
            e.created_at,
            null AS guest_uuid,
            false AS co_manager,
            null AS cohost_uuid
        FROM user_events e
        LEFT JOIN users u ON u.id = e.user_id
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
    events_owned_result = await fetch_all(sql_events_owned, (user_id, user_id, today, today, per_page, offset))
    if events_owned_result:
        events_owned: List[Dict[str, Any]] = list(events_owned_result)
    else:
        events_owned: List[Dict[str, Any]] = []

    # Events (cohost) — using ONLY exact columns from PHP model
    events_cohost: List[Dict[str, Any]] = []
    if user_email:
        sql_events_cohost = (
            """
            SELECT 
                e.id AS booking_id,
                e.id AS event_id,
                CONCAT('EVE-', LPAD(e.id, 5, '0')) AS id,
                CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, '')) AS business_name,
                'events' AS type,
                COALESCE(e.cover_image, 'N/A') AS img_url,
                COALESCE(e.title, 'Event') AS title,
                COALESCE(e.venue, 'N/A') AS location,
                '' AS tracking_number,
                COALESCE(e.uuid, '') AS uuid,
                COALESCE(e.event_date, 'N/A') AS event_date,
                COALESCE(e.start_time, 'N/A') AS start_time,
                COALESCE(e.end_time, 'N/A') AS end_time,
                COALESCE(e.guests, 0) AS guests,
                COALESCE(e.entry, 'free') AS entry_type,
                COALESCE(e.venue, 'N/A') AS venue,
                COALESCE(e.address, 'N/A') AS address,
                COALESCE(e.description, 'N/A') AS description,
                false AS owner,
                CASE WHEN e.entry = 'free' THEN null ELSE 'price' END AS price,
                '[]' AS ticket_types,
                0 AS total_bookings,
                0 AS completed_bookings,
                0 AS pending_bookings,
                0 AS total_revenue,
                false AS has_settlement,
                COALESCE(e.status, 'draft') AS status,
                e.created_at,
                null AS guest_uuid,
                true AS co_manager,
                null AS cohost_uuid
            FROM user_events e
            LEFT JOIN users u ON u.id = e.user_id
            LEFT JOIN user_event_cohosts c ON c.user_event_id = e.id AND c.email = %s
            WHERE EXISTS (
                SELECT 1 FROM user_event_cohosts c2
                WHERE c2.user_event_id = e.id AND c2.email = %s
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
        events_cohost_result = await fetch_all(sql_events_cohost, (user_email, user_email, today, today, per_page, offset))
        if events_cohost_result:
            events_cohost = list(events_cohost_result)
        else:
            events_cohost = []

    # Combine all bookings
    all_bookings = bookings + events_owned + events_cohost

    # Calculate total count for pagination - only count active bookings/events
    sql_total_count = (
        """
        SELECT COUNT(*) as total
        FROM (
            SELECT DISTINCT b.id
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
            
            UNION ALL
            
            SELECT DISTINCT e.id
            FROM user_events e
            WHERE e.user_id = %s
              AND EXISTS (
                SELECT 1 FROM user_event_dates d
                WHERE d.user_event_id = e.id
                  AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
              )
            
            UNION ALL
            
            SELECT DISTINCT e.id
            FROM user_events e
            WHERE EXISTS (
                SELECT 1 FROM user_event_cohosts c2
                WHERE c2.user_event_id = e.id AND c2.email = %s
            )
              AND EXISTS (
                SELECT 1 FROM user_event_dates d
                WHERE d.user_event_id = e.id
                  AND (d.date > %s OR (d.date = %s AND d.start_time > CURTIME()))
              )
        ) as combined
        """
    )
    total_result = await fetch_one(sql_total_count, (user_id, today, today, today, today, today, today, user_id, today, today, user_email, today, today))
    total_count = total_result["total"] if total_result else len(all_bookings)
    
    last_page = (total_count + per_page - 1) // per_page

    return {
        "bookings": all_bookings,
        "pagination": {
            "current_page": page,
            "per_page": per_page,
            "total": total_count,
            "last_page": last_page
        }
    }


