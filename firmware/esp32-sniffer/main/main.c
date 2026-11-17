/*
 * exam-uncheat ESP32 passive sensor firmware (v0.1, not yet hardware-tested)
 *
 * Targets: ESP32-S3, ESP32-C6 (2.4 GHz), ESP32-C5 (2.4 + 5 GHz). ESP-IDF >= 5.3.
 * Output : exam-uncheat line-JSON (NDJSON) on the USB serial console, one object per line.
 *
 * RECEIVE-ONLY POLICY (enforced by tools/no_tx_check.py in CI):
 *   - BLE: NimBLE observer, passive discovery (no SCAN_REQ). Never advertises or connects.
 *   - Wi-Fi: WIFI_MODE_NULL + promiscuous receive. Never scans actively, never sends frames.
 *   - Data frames: only transmitter address, frame count, byte count and RSSI are kept.
 *     The payload is never parsed or stored.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#if CONFIG_EXU_ENABLE_WIFI
#include "esp_wifi.h"
#endif
#if CONFIG_EXU_ENABLE_BLE
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#endif

#define FW_VERSION  "0.1.0"
#define OUT_LINE_MAX    420
#define MAX_STA     32

static QueueHandle_t s_q;
static volatile uint32_t s_dropped;
static char s_sensor_id[32];
typedef struct { char line[OUT_LINE_MAX]; } out_line_t;

static inline long long now_ms(void) { return (long long)(esp_timer_get_time() / 1000); }

/* Lines are queued and written by one task so radio callbacks never block on the UART. */
static void emit(const char *s) {
    out_line_t o;
    strlcpy(o.line, s, sizeof(o.line));
    if (xQueueSend(s_q, &o, 0) != pdTRUE) s_dropped++;
}

static void json_escape(const uint8_t *in, int len, char *out, int outsz) {
    int j = 0;
    for (int i = 0; i < len && j < outsz - 7; i++) {
        uint8_t c = in[i];
        if (c == '"' || c == '\\') { out[j++] = '\\'; out[j++] = (char)c; }
        else if (c < 0x20 || c == 0x7f) { j += snprintf(out + j, outsz - j, "\\u%04x", c); }
        else { out[j++] = (char)c; }  /* UTF-8 bytes pass through unchanged */
    }
    out[j] = 0;
}

static void hexstr(const uint8_t *in, int len, char *out, int max_bytes) {
    int n = len < max_bytes ? len : max_bytes;
    for (int i = 0; i < n; i++) snprintf(out + 2 * i, 3, "%02x", in[i]);
    out[2 * (n > 0 ? n : 0)] = 0;
}

static void mac_str(const uint8_t *m, char *out) {
    snprintf(out, 18, "%02x:%02x:%02x:%02x:%02x:%02x", m[0], m[1], m[2], m[3], m[4], m[5]);
}

/* ------------------------------------------------------------------ BLE -- */
#if CONFIG_EXU_ENABLE_BLE
static int ble_gap_event(struct ble_gap_event *ev, void *arg) {
    if (ev->type != BLE_GAP_EVENT_DISC) return 0;
    const struct ble_gap_disc_desc *d = &ev->disc;
    struct ble_hs_adv_fields f;
    memset(&f, 0, sizeof(f));
    if (ble_hs_adv_parse_fields(&f, d->data, d->length_data) != 0) return 0;

    char addr[18], attrs[300], tmp[72];
    uint8_t a[6];
    for (int i = 0; i < 6; i++) a[i] = d->addr.val[5 - i];   /* NimBLE stores addresses little-endian */
    mac_str(a, addr);

    int p = snprintf(attrs, sizeof(attrs), "\"connectable\":%s",
                     d->event_type == BLE_HCI_ADV_RPT_EVTYPE_ADV_IND ? "true" : "false");
    if (f.mfg_data && f.mfg_data_len >= 2) {
        int cid = f.mfg_data[0] | (f.mfg_data[1] << 8);
        hexstr(f.mfg_data + 2, f.mfg_data_len - 2, tmp, 32);
        p += snprintf(attrs + p, sizeof(attrs) - p, ",\"company_id\":%d,\"mfg_data_hex\":\"%s\"", cid, tmp);
    }
    if (f.name && f.name_len && p < (int)sizeof(attrs) - 80) {
        json_escape(f.name, f.name_len, tmp, sizeof(tmp));
        p += snprintf(attrs + p, sizeof(attrs) - p, ",\"name\":\"%s\"", tmp);
    }
    if (f.num_uuids16 && p < (int)sizeof(attrs) - 20) {
        p += snprintf(attrs + p, sizeof(attrs) - p, ",\"service_uuids\":[");
        for (int i = 0; i < f.num_uuids16 && p < (int)sizeof(attrs) - 12; i++)
            p += snprintf(attrs + p, sizeof(attrs) - p, "%s\"%04x\"", i ? "," : "", f.uuids16[i].value);
        p += snprintf(attrs + p, sizeof(attrs) - p, "]");
    }
    if (f.svc_data_uuid16 && f.svc_data_uuid16_len >= 2 && p < (int)sizeof(attrs) - 60) {
        int u = f.svc_data_uuid16[0] | (f.svc_data_uuid16[1] << 8);
        hexstr(f.svc_data_uuid16 + 2, f.svc_data_uuid16_len - 2, tmp, 16);
        p += snprintf(attrs + p, sizeof(attrs) - p, ",\"service_data\":{\"%04x\":\"%s\"}", u, tmp);
    }
    if (p >= (int)sizeof(attrs)) return 0;   /* truncated: drop rather than emit broken JSON */

    char line[OUT_LINE_MAX];
    int n = snprintf(line, sizeof(line),
        "{\"kind\":\"ble.adv\",\"sensor_ts_ms\":%lld,\"rssi_dbm\":%d,"
        "\"subject\":{\"addr\":\"%s\",\"addr_type\":\"%s\"},\"attrs\":{%s}}",
        now_ms(), d->rssi, addr, d->addr.type == BLE_ADDR_PUBLIC ? "public" : "random", attrs);
    if (n > 0 && n < (int)sizeof(line)) emit(line);
    return 0;
}

static void ble_start_passive_scan(void) {
    uint8_t own_type;
    if (ble_hs_id_infer_auto(0, &own_type) != 0) own_type = BLE_OWN_ADDR_PUBLIC;
    struct ble_gap_disc_params dp;
    memset(&dp, 0, sizeof(dp));
    dp.passive = 1;              /* REQUIRED: passive scanning sends no SCAN_REQ */
    dp.filter_duplicates = 0;    /* repeated adverts are needed for persistence and RSSI */
    dp.itvl = 0x0060;            /* 60 ms */
    dp.window = 0x0030;          /* 30 ms: leaves radio time for Wi-Fi when both are enabled */
    int rc = ble_gap_disc(own_type, BLE_HS_FOREVER, &dp, ble_gap_event, NULL);
    if (rc != 0) {
        char line[96];
        snprintf(line, sizeof(line), "{\"kind\":\"sensor.health\",\"sensor_ts_ms\":%lld,\"attrs\":{\"ble_error\":%d}}", now_ms(), rc);
        emit(line);
    }
}

static void ble_on_sync(void) { ble_start_passive_scan(); }
static void ble_on_reset(int reason) { (void)reason; }
static void ble_host_task(void *arg) { nimble_port_run(); nimble_port_freertos_deinit(); }
#endif

/* ----------------------------------------------------------------- Wi-Fi -- */
#if CONFIG_EXU_ENABLE_WIFI
typedef struct { uint8_t mac[6]; uint32_t frames, bytes; int8_t rssi_max; uint8_t used; } sta_t;
static sta_t s_sta[MAX_STA];
static volatile uint8_t s_channel = 1;
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

static const uint8_t CHANNELS[] = {
    1, 6, 11, 2, 7, 12, 3, 8, 13, 4, 9, 5, 10,   /* common channels first */
#if CONFIG_EXU_SCAN_5G
    36, 40, 44, 48, 149, 153, 157, 161, 52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 165,
#endif
};

static int has_p2p_ie(const uint8_t *ie, int len) {
    while (len >= 2) {
        int id = ie[0], l = ie[1];
        if (l + 2 > len) break;
        /* Vendor IE, WFA OUI 50:6f:9a, OUI type 0x09 = Wi-Fi P2P */
        if (id == 221 && l >= 4 && ie[2] == 0x50 && ie[3] == 0x6f && ie[4] == 0x9a && ie[5] == 0x09) return 1;
        ie += l + 2; len -= l + 2;
    }
    return 0;
}

static void ssid_of(const uint8_t *ie, int len, char *out, int outsz) {
    out[0] = 0;
    if (len >= 2 && ie[0] == 0 && ie[1] <= 32 && ie[1] + 2 <= len) json_escape(ie + 2, ie[1], out, outsz);
}

static void wifi_rx_cb(void *buf, wifi_promiscuous_pkt_type_t type) {
    const wifi_promiscuous_pkt_t *pkt = buf;
    const uint8_t *fr = pkt->payload;
    int len = pkt->rx_ctrl.sig_len;          /* includes the 4-byte FCS */
    if (len < 28) return;
    uint8_t fc0 = fr[0];
    int ftype = (fc0 >> 2) & 3, subtype = (fc0 >> 4) & 0xF;

    if (type == WIFI_PKT_MGMT && ftype == 0 && (subtype == 4 || subtype == 8)) {
        char line[OUT_LINE_MAX], mac[18], bssid[18], ssid[200];
        int hdr = (subtype == 8) ? 36 : 24;    /* beacon: 24 header + 12 fixed fields */
        int ielen = len - hdr - 4;
        if (ielen < 0) return;
        const uint8_t *ie = fr + hdr;
        mac_str(fr + 10, mac);
        ssid_of(ie, ielen, ssid, sizeof(ssid));
        int p2p = has_p2p_ie(ie, ielen);
        int la = fr[10] & 0x02;                /* locally administered (randomised) address */
        int n;
        if (subtype == 4) {
            n = snprintf(line, sizeof(line),
                "{\"kind\":\"wifi.probe_req\",\"sensor_ts_ms\":%lld,\"channel\":%d,\"rssi_dbm\":%d,"
                "\"subject\":{\"addr\":\"%s\",\"addr_type\":\"%s\"},\"attrs\":{\"ssid\":\"%s\",\"is_wildcard\":%s,\"p2p_ie\":%s}}",
                now_ms(), s_channel, pkt->rx_ctrl.rssi, mac, la ? "random" : "public",
                ssid, ssid[0] ? "false" : "true", p2p ? "true" : "false");
        } else {
            mac_str(fr + 16, bssid);
            n = snprintf(line, sizeof(line),
                "{\"kind\":\"wifi.beacon\",\"sensor_ts_ms\":%lld,\"channel\":%d,\"rssi_dbm\":%d,"
                "\"subject\":{\"addr\":\"%s\",\"addr_type\":\"%s\"},\"attrs\":{\"ssid\":\"%s\",\"bssid\":\"%s\",\"hidden\":%s,\"is_p2p_go\":%s}}",
                now_ms(), s_channel, pkt->rx_ctrl.rssi, mac, la ? "random" : "public",
                ssid, bssid, ssid[0] ? "false" : "true", p2p ? "true" : "false");
        }
        if (n > 0 && n < (int)sizeof(line)) emit(line);
    } else if (type == WIFI_PKT_DATA) {
        /* Count only. The payload is never read. */
        const uint8_t *ta = fr + 10;
        portENTER_CRITICAL(&s_mux);
        int slot = -1;
        for (int i = 0; i < MAX_STA; i++) {
            if (s_sta[i].used && !memcmp(s_sta[i].mac, ta, 6)) { slot = i; break; }
            if (!s_sta[i].used && slot < 0) slot = i;
        }
        if (slot >= 0) {
            sta_t *s = &s_sta[slot];
            if (!s->used) { memcpy(s->mac, ta, 6); s->used = 1; s->rssi_max = -127; }
            s->frames++; s->bytes += (uint32_t)len;
            if (pkt->rx_ctrl.rssi > s->rssi_max) s->rssi_max = pkt->rx_ctrl.rssi;
        }
        portEXIT_CRITICAL(&s_mux);
    }
}

static void hop_task(void *arg) {
    size_t i = 0;
    for (;;) {
        s_channel = CHANNELS[i];
        esp_wifi_set_channel(s_channel, WIFI_SECOND_CHAN_NONE);
        i = (i + 1) % sizeof(CHANNELS);
        vTaskDelay(pdMS_TO_TICKS(CONFIG_EXU_DWELL_MS));
    }
}

static void flush_station_stats(void) {
    static sta_t snap[MAX_STA];
    portENTER_CRITICAL(&s_mux);
    memcpy(snap, s_sta, sizeof(snap));
    memset(s_sta, 0, sizeof(s_sta));
    portEXIT_CRITICAL(&s_mux);
    for (int i = 0; i < MAX_STA; i++) {
        if (!snap[i].used) continue;
        char mac[18], line[320];
        mac_str(snap[i].mac, mac);
        snprintf(line, sizeof(line),
            "{\"kind\":\"wifi.station\",\"sensor_ts_ms\":%lld,\"rssi_dbm\":%d,\"subject\":{\"addr\":\"%s\",\"addr_type\":\"%s\"},"
            "\"attrs\":{\"frames\":%lu,\"bytes\":%lu,\"window_s\":%d}}",
            now_ms(), snap[i].rssi_max, mac, (snap[i].mac[0] & 2) ? "random" : "public",
            (unsigned long)snap[i].frames, (unsigned long)snap[i].bytes, CONFIG_EXU_STATS_PERIOD_S);
        emit(line);
    }
}

static void wifi_start_passive(void) {
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_NULL));   /* no STA/AP interface exists */
    ESP_ERROR_CHECK(esp_wifi_start());
    wifi_promiscuous_filter_t filt = {.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA};
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&filt));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_rx_cb(wifi_rx_cb));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));
    xTaskCreate(hop_task, "hop", 2048, NULL, 5, NULL);
}
#endif

/* ----------------------------------------------------------------- main --- */
static void writer_task(void *arg) {
    out_line_t o;
    for (;;) {
        if (xQueueReceive(s_q, &o, portMAX_DELAY) == pdTRUE) {
            fputs(o.line, stdout);
            fputc('\n', stdout);
            fflush(stdout);
        }
    }
}

static void health_task(void *arg) {
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(CONFIG_EXU_STATS_PERIOD_S * 1000));
#if CONFIG_EXU_ENABLE_WIFI
        flush_station_stats();
#endif
        char line[200];
        snprintf(line, sizeof(line),
            "{\"kind\":\"sensor.health\",\"sensor_ts_ms\":%lld,\"attrs\":{\"uptime_s\":%lld,\"dropped\":%lu,\"free_heap\":%lu}}",
            now_ms(), now_ms() / 1000, (unsigned long)s_dropped, (unsigned long)esp_get_free_heap_size());
        emit(line);
    }
}

static void make_sensor_id(void) {
    uint8_t m[6] = {0};
    esp_read_mac(m, ESP_MAC_BASE);   /* the sensor's own factory address, not an observed device */
    snprintf(s_sensor_id, sizeof(s_sensor_id), "%s-%02x%02x%02x", CONFIG_IDF_TARGET, m[3], m[4], m[5]);
}

void app_main(void) {
    esp_log_level_set("*", ESP_LOG_WARN);  /* keep the console almost pure JSON */
    esp_err_t r = nvs_flash_init();
    if (r == ESP_ERR_NVS_NO_FREE_PAGES || r == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }
    make_sensor_id();
    s_q = xQueueCreate(64, sizeof(out_line_t));
    xTaskCreate(writer_task, "writer", 4096, NULL, 3, NULL);

    char caps[96] = "";
#if CONFIG_EXU_ENABLE_BLE
    strlcat(caps, "\"ble.adv\"", sizeof(caps));
#endif
#if CONFIG_EXU_ENABLE_WIFI
    strlcat(caps, caps[0] ? ",\"wifi.mgmt\",\"wifi.data_stats\"" : "\"wifi.mgmt\",\"wifi.data_stats\"", sizeof(caps));
#endif
#if CONFIG_EXU_SCAN_5G
    const char *band5 = ",\"5GHz\"";
#else
    const char *band5 = "";
#endif
    char hello[OUT_LINE_MAX];
    snprintf(hello, sizeof(hello),
        "{\"schema\":\"exam-uncheat.hello/v1\",\"sensor_id\":\"%s\",\"driver\":\"esp32-sniffer\",\"driver_version\":\"%s\","
        "\"hw\":\"%s\",\"capabilities\":[%s],\"bands\":[\"2.4GHz\"%s],\"tx_capable\":false}",
        s_sensor_id, FW_VERSION, CONFIG_IDF_TARGET, caps, band5);
    emit(hello);

#if CONFIG_EXU_ENABLE_WIFI
    wifi_start_passive();
#endif
#if CONFIG_EXU_ENABLE_BLE
    ESP_ERROR_CHECK(nimble_port_init());
    ble_hs_cfg.sync_cb = ble_on_sync;
    ble_hs_cfg.reset_cb = ble_on_reset;
    nimble_port_freertos_init(ble_host_task);
#endif
    xTaskCreate(health_task, "health", 4096, NULL, 2, NULL);
}
