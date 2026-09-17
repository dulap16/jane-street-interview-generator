"""Private, complete reference for the familiar reservation-ledger demo."""


class Solution:
    def __init__(self, capacities: dict[str, int]):
        if any(value < 0 for value in capacities.values()):
            raise ValueError("capacities must be nonnegative")
        self._capacities = dict(capacities)
        self._free = dict(capacities)
        self._active: dict[str, tuple[str, int]] = {}

    def remaining(self, bay: str) -> int:
        return self._free[bay]

    def reserve(self, reservation_id: str, bay: str, units: int) -> bool:
        if not reservation_id or units <= 0:
            raise ValueError("an ID and positive units are required")
        if bay not in self._free:
            raise KeyError(bay)
        if reservation_id in self._active:
            raise ValueError("reservation ID is already active")
        if self._free[bay] < units:
            return False
        self._free[bay] -= units
        self._active[reservation_id] = (bay, units)
        return True

    def cancel(self, reservation_id: str) -> bool:
        if not reservation_id:
            raise ValueError("an ID is required")
        booking = self._active.pop(reservation_id, None)
        if booking is None:
            return False
        bay, units = booking
        self._free[bay] += units
        return True

    def allocation(self, reservation_id: str) -> dict[str, int] | None:
        if not reservation_id:
            raise ValueError("an ID is required")
        booking = self._active.get(reservation_id)
        if booking is None:
            return None
        bay, units = booking
        return {bay: units}

    def replace(
        self,
        cancel_ids: list[str],
        new_ids: list[str],
        bays: list[str],
        units: list[int],
    ) -> bool:
        if (
            len(new_ids) != len(bays)
            or len(new_ids) != len(units)
            or any(not value for value in cancel_ids)
            or any(not value for value in new_ids)
            or any(value <= 0 for value in units)
            or len(set(cancel_ids)) != len(cancel_ids)
            or len(set(new_ids)) != len(new_ids)
        ):
            raise ValueError("malformed batch")
        if any(value not in self._active for value in cancel_ids):
            raise KeyError("unknown cancellation ID")
        if any(bay not in self._free for bay in bays):
            raise KeyError("unknown bay")
        cancellations = set(cancel_ids)
        if any(
            value in self._active and value not in cancellations for value in new_ids
        ):
            raise ValueError("reservation ID is already active")

        available = dict(self._free)
        for reservation_id in cancel_ids:
            bay, amount = self._active[reservation_id]
            available[bay] += amount
        for bay, amount in zip(bays, units):
            if available[bay] < amount:
                return False
            available[bay] -= amount

        for reservation_id in cancel_ids:
            del self._active[reservation_id]
        for reservation_id, bay, amount in zip(new_ids, bays, units):
            self._active[reservation_id] = (bay, amount)
        self._free = available
        return True
