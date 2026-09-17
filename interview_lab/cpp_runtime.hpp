#ifndef INTERVIEW_LAB_CPP_RUNTIME_HPP
#define INTERVIEW_LAB_CPP_RUNTIME_HPP

#include <cstdint>
#include <cstdlib>
#include <exception>
#include <fstream>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace interview_lab_detail {

inline bool valid_utf8(const std::string& text) {
    for (std::size_t i = 0; i < text.size();) {
        auto first = static_cast<unsigned char>(text[i++]);
        if (first < 0x80) continue;
        unsigned code = 0, minimum = 0, remaining = 0;
        if (first >= 0xc2 && first <= 0xdf) {
            code = first & 0x1f; remaining = 1; minimum = 0x80;
        } else if (first >= 0xe0 && first <= 0xef) {
            code = first & 0x0f; remaining = 2; minimum = 0x800;
        } else if (first >= 0xf0 && first <= 0xf4) {
            code = first & 0x07; remaining = 3; minimum = 0x10000;
        } else return false;
        if (remaining > text.size() - i) return false;
        while (remaining--) {
            auto next = static_cast<unsigned char>(text[i++]);
            if ((next & 0xc0) != 0x80) return false;
            code = (code << 6) | (next & 0x3f);
        }
        if (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return false;
    }
    return true;
}

struct encoding_error : std::exception {
    const char* what() const noexcept override { return "return or mutation exceeds typed value limits, or contains invalid UTF-8"; }
};

struct json_buffer {
    std::string text;
    std::size_t nodes = 0;
    void add(const std::string& value) {
        if (value.size() > 16 * 1024 * 1024 - text.size()) throw encoding_error{};
        text += value;
    }
    void node() { if (++nodes > 100000) throw encoding_error{}; }
};

inline void quoted(json_buffer& out, const std::string& text) {
    if (text.size() > 1048576 || !valid_utf8(text)) throw encoding_error{};
    static const char digits[] = "0123456789abcdef";
    out.add("\"");
    for (unsigned char ch : text) {
        if (ch == '"' || ch == '\\') {
            out.add(std::string("\\") + static_cast<char>(ch));
        } else if (ch < 0x20) {
            std::string escaped = "\\u00";
            escaped += digits[ch >> 4];
            escaped += digits[ch & 15];
            out.add(escaped);
        } else out.add(std::string(1, static_cast<char>(ch)));
    }
    out.add("\"");
}

inline void encode(json_buffer& out, const std::int64_t& value);
inline void encode(json_buffer& out, const bool& value);
inline void encode(json_buffer& out, const std::string& value);
template<class T> void encode(json_buffer& out, const std::vector<T>& value);
template<class T> void encode(json_buffer& out, const std::optional<T>& value);
template<class T> void encode(json_buffer& out, const std::map<std::string, T>& value);

inline void encode(json_buffer& out, const std::int64_t& value) {
    out.node(); out.add(std::to_string(value));
}
inline void encode(json_buffer& out, const bool& value) {
    out.node(); out.add(value ? "true" : "false");
}
inline void encode(json_buffer& out, const std::string& value) {
    out.node(); quoted(out, value);
}
template<class T> void encode(json_buffer& out, const std::vector<T>& value) {
    out.node();
    if (value.size() > 10000) throw encoding_error{};
    out.add("[");
    bool first = true;
    for (const T& item : value) {
        if (!first) out.add(",");
        first = false;
        encode(out, item);
    }
    out.add("]");
}
template<class T> void encode(json_buffer& out, const std::optional<T>& value) {
    out.node();
    if (value) encode(out, *value);
    else out.add("null");
}
template<class T> void encode(json_buffer& out, const std::map<std::string, T>& value) {
    out.node();
    if (value.size() > 10000) throw encoding_error{};
    out.add("{");
    bool first = true;
    for (const auto& item : value) {
        if (!first) out.add(",");
        first = false;
        quoted(out, item.first);
        out.add(":");
        encode(out, item.second);
    }
    out.add("}");
}

inline std::string json_string(const std::string& value) {
    json_buffer out;
    quoted(out, value);
    return out.text;
}

template<class T> std::string value_outcome(const T& value) {
    try {
        json_buffer out;
        encode(out, value);
        return "{\"kind\":\"value\",\"value\":" + out.text + "}";
    } catch (const encoding_error&) {
        return "{\"kind\":\"invalid\",\"message\":\"invalid typed value or UTF-8\"}";
    }
}

inline std::string exception_outcome(const char* category, const char* type, const char* message) {
    std::string text;
    if (message) {
        for (std::size_t i = 0; i < 2048 && message[i]; ++i) text += message[i];
    }
    if (!valid_utf8(text)) text = "<exception message is not valid UTF-8>";
    return "{\"kind\":\"exception\",\"category\":" + json_string(category)
        + ",\"type\":" + json_string(type) + ",\"message\":" + json_string(text) + "}";
}

template<class F> std::string invoke(F&& function) {
    try {
        if constexpr (std::is_void_v<decltype(function())>) {
            function();
            return "{\"kind\":\"value\",\"value\":null}";
        } else return value_outcome(function());
    } catch (const std::invalid_argument& error) {
        return exception_outcome("invalid_argument", "std::invalid_argument", error.what());
    } catch (const std::out_of_range& error) {
        return exception_outcome("out_of_range", "std::out_of_range", error.what());
    } catch (const std::runtime_error& error) {
        return exception_outcome("runtime_error", "std::runtime_error", error.what());
    } catch (const std::exception& error) {
        return exception_outcome("other", "std::exception", error.what());
    } catch (...) {
        return exception_outcome("other", "unknown", "non-standard C++ exception");
    }
}

class protocol_writer {
    std::ofstream stream;
    std::size_t remaining;
public:
    protocol_writer(const char* path, std::size_t limit)
        : stream(path, std::ios::binary | std::ios::trunc), remaining(limit + 1) {
        if (!stream) std::_Exit(87);
    }
    void write(const std::string& text) {
        const auto count = text.size() < remaining ? text.size() : remaining;
        stream.write(text.data(), static_cast<std::streamsize>(count));
        stream.flush();
        if (!stream) std::_Exit(87);
        remaining -= count;
        if (!remaining) std::_Exit(86);
    }
};

} // namespace interview_lab_detail
#endif
