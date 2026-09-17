// Private, complete reference for the familiar reservation-ledger demo.
#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

class Solution {
    using Integer = std::int64_t;
    std::map<std::string, Integer> free_;
    std::map<std::string, std::pair<std::string, Integer>> active_;

public:
    explicit Solution(std::map<std::string, Integer> capacities)
        : free_(std::move(capacities)) {
        for (const auto& entry : free_) {
            if (entry.second < 0) {
                throw std::invalid_argument("capacities must be nonnegative");
            }
        }
    }

    Integer remaining(std::string bay) { return free_.at(bay); }

    bool reserve(std::string reservation_id, std::string bay, Integer units) {
        if (reservation_id.empty() || units <= 0) {
            throw std::invalid_argument("an ID and positive units are required");
        }
        if (!free_.count(bay)) {
            throw std::out_of_range("unknown bay");
        }
        if (active_.count(reservation_id)) {
            throw std::invalid_argument("reservation ID is already active");
        }
        if (free_.at(bay) < units) {
            return false;
        }
        free_.at(bay) -= units;
        active_.emplace(reservation_id, std::make_pair(bay, units));
        return true;
    }

    bool cancel(std::string reservation_id) {
        if (reservation_id.empty()) {
            throw std::invalid_argument("an ID is required");
        }
        const auto found = active_.find(reservation_id);
        if (found == active_.end()) {
            return false;
        }
        free_.at(found->second.first) += found->second.second;
        active_.erase(found);
        return true;
    }

    std::optional<std::map<std::string, Integer>>
    allocation(std::string reservation_id) {
        if (reservation_id.empty()) {
            throw std::invalid_argument("an ID is required");
        }
        const auto found = active_.find(reservation_id);
        if (found == active_.end()) {
            return std::nullopt;
        }
        return std::map<std::string, Integer>{
            {found->second.first, found->second.second}};
    }

    bool replace(std::vector<std::string> cancel_ids,
                 std::vector<std::string> new_ids,
                 std::vector<std::string> bays,
                 std::vector<Integer> units) {
        if (new_ids.size() != bays.size() || new_ids.size() != units.size()) {
            throw std::invalid_argument("batch lengths differ");
        }
        std::set<std::string> cancellations;
        std::set<std::string> additions;
        for (const auto& id : cancel_ids) {
            if (id.empty() || !cancellations.insert(id).second) {
                throw std::invalid_argument("invalid cancellation IDs");
            }
        }
        for (const auto& id : new_ids) {
            if (id.empty() || !additions.insert(id).second) {
                throw std::invalid_argument("invalid new IDs");
            }
        }
        for (const auto amount : units) {
            if (amount <= 0) {
                throw std::invalid_argument("units must be positive");
            }
        }
        for (const auto& id : cancel_ids) {
            if (!active_.count(id)) {
                throw std::out_of_range("unknown cancellation ID");
            }
        }
        for (const auto& bay : bays) {
            if (!free_.count(bay)) {
                throw std::out_of_range("unknown bay");
            }
        }
        for (const auto& id : new_ids) {
            if (active_.count(id) && !cancellations.count(id)) {
                throw std::invalid_argument("reservation ID is already active");
            }
        }

        auto available = free_;
        for (const auto& id : cancel_ids) {
            const auto& booking = active_.at(id);
            available.at(booking.first) += booking.second;
        }
        // Subtraction checks avoid overflowing even when request totals exceed int64.
        for (std::size_t index = 0; index < new_ids.size(); ++index) {
            auto& remaining_units = available.at(bays[index]);
            if (remaining_units < units[index]) {
                return false;
            }
            remaining_units -= units[index];
        }
        for (const auto& id : cancel_ids) {
            active_.erase(id);
        }
        for (std::size_t index = 0; index < new_ids.size(); ++index) {
            active_.emplace(new_ids[index],
                            std::make_pair(bays[index], units[index]));
        }
        free_ = std::move(available);
        return true;
    }
};
