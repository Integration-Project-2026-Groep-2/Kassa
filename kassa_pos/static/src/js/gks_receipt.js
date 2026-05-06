/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

// Runtime load marker
console.info('[kassa_pos] gks_receipt.js loaded');
window.__kassa_pos_gks_loaded = true;

// Product category mapping: product name → tax rate (%)
const PRODUCT_CATEGORIES = {
    // Food (6% VAT)
    "pizza": 6,
    "sandwich": 6,
    "fries": 6,
    "burger": 6,
    
    // Drinks (21% VAT - alcoholic)
    "beer": 21,
    "soda": 21,
    "water": 21,
    "coffee": 21,
};

function toNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function parseCurrency(value) {
    // Handle "8.40 €" or "2.80 €" formatted strings
    if (typeof value === 'string') {
        const numStr = value.replace(/[^\d.,]/g, '').replace(',', '.');
        return toNumber(numStr);
    }
    return toNumber(value);
}

function getLineRate(line) {
    // 1) Try tax_ids if available
    const directRate = toNumber(line?.tax_ids?.[0]?.amount ?? line?.taxes?.[0]?.amount);
    if (directRate) {
        return Math.round(directRate) === 6 ? 6 : 21;
    }

    // 2) Try tax label
    const label = String(line?.taxGroupLabels || line?.tax_label || "").toLowerCase();
    if (label.includes("6")) {
        return 6;
    }
    if (label.includes("21")) {
        return 21;
    }

    // 3) Map by product name
    const productName = (line?.productName || line?.name || "").toLowerCase().trim();
    if (PRODUCT_CATEGORIES[productName] !== undefined) {
        return PRODUCT_CATEGORIES[productName];
    }

    // 4) Default to 21% for alcoholic beverages (drinks)
    if (productName.includes("drink") || productName.includes("beer") || productName.includes("soda") || productName.includes("coffee")) {
        return 21;
    }

    // 5) Default to 6% for food
    if (productName.includes("food") || productName.includes("pizza") || productName.includes("burger") || productName.includes("sandwich") || productName.includes("fries")) {
        return 6;
    }

    return 21; // Ultimate default
}

function getLineGross(line) {
    // Prefer explicit fields if present; avoid parseCurrency returning 0 for undefined
    if (line?.price != null) {
        return toNumber(parseCurrency(line.price));
    }
    if (line?.price_subtotal_incl != null) {
        return toNumber(line.price_subtotal_incl);
    }
    if (line?.prices?.total_included != null) {
        return toNumber(line.prices.total_included);
    }
    if (line?.total_included != null) {
        return toNumber(line.total_included);
    }
    // Fallback to unit price * qty
    return toNumber((line?.price_unit ?? line?.unitPrice ?? line?.unit_price) * toNumber(line?.qty));
}

function getLineNet(line) {
    // Prefer an explicit net value only if it appears to be a true net (smaller than gross).
    const gross = getLineGross(line);
    const rate = getLineRate(line);

    const explicitNetCandidate = (line?.price_without_discount != null)
        ? parseCurrency(line.price_without_discount)
        : (line?.price_subtotal != null ? parseCurrency(line.price_subtotal) : null);

    if (explicitNetCandidate != null && explicitNetCandidate > 0) {
        // If the explicit candidate is meaningfully smaller than gross, trust it as net.
        if (explicitNetCandidate < gross - 0.001) {
            return toNumber(explicitNetCandidate);
        }
        // Otherwise ignore it (it was likely a gross value masquerading as subtotal).
    }

    // Fallback: compute net from gross and rate
    return toNumber(gross / (1.0 + (rate / 100.0)));
}

function getLineVatAmount(line) {
    const gross = getLineGross(line);
    const net = getLineNet(line);
    const vat = gross - net;
    return Number.isFinite(vat) ? vat : 0;
}

patch(OrderReceipt.prototype, {
    setup() {
        if (super.setup) {
            super.setup(...arguments);
        }

        const initialVscCode = this.props?.data?.vsc_code || this.props?.data?.gks_vsc || "";
        this.gksReceiptState = useState({
            vscCode: initialVscCode,
        });

        onWillStart(async () => {
            if (this.gksReceiptState.vscCode) {
                return;
            }

            let orderId = this.props?.order?.server_id || this.props?.data?.id || this.props?.data?.server_id || this.props?.data?.gks_order_id;
            if (!orderId && this.props?.data?.name) {
                const nameMatch = this.props.data.name.match(/(\d+)/);
                if (nameMatch) {
                    orderId = parseInt(nameMatch[0]);
                }
            }

            if (!orderId) {
                return;
            }

            try {
                const result = await this.env.services.rpc('/kassa_pos/get_vsc_code', { order_id: orderId });
                if (result && result.vsc_code) {
                    this._cachedVscCode = result.vsc_code;
                    this.gksReceiptState.vscCode = result.vsc_code;
                    if (this.props?.data) {
                        this.props.data.vsc_code = result.vsc_code;
                    }
                }
            } catch (error) {
                console.error('[kassa_pos] ❌ RPC fetch failed:', error);
            }
        });
    },

    get receipt() {
        const data = this.props?.data || {};
        // Use cached VSC if available (from RPC fetch), otherwise from data, otherwise empty
        const vscCode = this.gksReceiptState?.vscCode || this._cachedVscCode || data.vsc_code || data.gks_vsc || "";
        console.log('[kassa_pos] receipt getter called - vscCode:', vscCode, 'cached:', this._cachedVscCode, 'data.vsc_code:', data.vsc_code);
        return {
            ...data,
            vsc_code: vscCode,
            gks_vsc: data.gks_vsc || vscCode,
        };
    },

    get gksCompanyName() {
        return "Desiderius Hogeschool";
    },

    get gksCompanyAddress() {
        return "Straatnaam 1, 1000 Brussel";
    },

    get gksVatNumber() {
        return "BE 0123.456.789";
    },

    get gksVsc() {
        return this.gksReceiptState?.vscCode || this.props?.data?.vsc_code || this.props?.data?.gks_vsc || this._cachedVscCode || "";
    },

    get gksReceiptLines() {
        let order = this.order || this.props?.order;

        // If order not available on the component, try the `data` prop (export_for_printing())
        const printedData = this.props?.data;
        if (!order && printedData) {
            console.debug('[kassa_pos] gksReceiptLines - using props.data');
        }

        // Attempt to fetch server-side VAT breakdown for synced orders.
        // If the receipt component has access to a server-backed order object
        // (props.order) or the printed data contains an order id, request the
        // authoritative breakdown and cache it on the component instance.
        const serverId = this.props?.order?.backendId || this.props?.order?.server_id || printedData?.server_id || printedData?.backendId || printedData?.id;
        if (serverId && !this._gksServerBreakdownFetched) {
            this._gksServerBreakdownFetched = true;
            (async () => {
                try {
                    const resp = await this.env.services.rpc('/kassa_pos/get_gks_vat_breakdown', { order_id: serverId });
                    if (resp && resp.ok && resp.breakdown) {
                        this._gksServerBreakdown = resp.breakdown;
                        console.debug('[kassa_pos] fetched server gks_vat_breakdown', resp.breakdown);
                    } else {
                        console.debug('[kassa_pos] server breakdown not available', resp && resp.error);
                    }
                } catch (err) {
                    console.warn('[kassa_pos] failed to fetch server gks_vat_breakdown', err);
                }
            })();
        }

        // As a last resort, try to read the active POS order from the environment
        const posOrderCandidate = (!order && !printedData && this.env?.pos && typeof this.env.pos.get_order === 'function') ? this.env.pos.get_order() : undefined;

        const raw =
            // 1) Order object with arrays
            order?.lines ??
            order?.line_ids ??
            order?.orderlines ??
            // 2) Printed/exported data shape (export_for_printing)
            printedData?.lines ??
            printedData?.line_ids ??
            printedData?.orderlines ??
            printedData?.order_lines ??
            // 3) POS Order instance methods
            (order && typeof order?.get_orderlines === 'function' ? order.get_orderlines() : undefined) ??
            // 4) active pos order candidate
            (posOrderCandidate && (typeof posOrderCandidate.get_orderlines === 'function' ? posOrderCandidate.get_orderlines() : posOrderCandidate.orderlines)) ??
            [];

        // Log raw exported shape for easier debugging in DevTools
        try {
            if (Array.isArray(raw)) {
                console.debug('[kassa_pos] raw orderlines length', raw.length, 'first:', raw[0]);
            } else {
                console.debug('[kassa_pos] raw orderlines (non-array)', raw);
            }
        } catch (e) {
            console.warn('[kassa_pos] failed to log raw orderlines', e);
        }

        const normalized = (raw || []).map((l, idx) => {
            const qty = parseCurrency(l?.qty ?? l?.quantity ?? l?.qty_order ?? (typeof l?.get_quantity === "function" ? l.get_quantity() : undefined)) || 0;
            const price_unit = parseCurrency(l?.unitPrice ?? l?.price_unit ?? l?.unit_price ?? (typeof l?.get_unit_price === "function" ? l.get_unit_price() : undefined)) || 0;
            const price_subtotal_incl = parseCurrency(l?.price ?? l?.price_subtotal_incl ?? l?.prices?.total_included ?? l?.total_included ?? (typeof l?.get_price_included === "function" ? l.get_price_included() : undefined)) || (price_unit * qty);
                const raw_price_without_discount = parseCurrency(l?.price_without_discount ?? l?.price_subtotal ?? l?.prices?.total_excluded ?? l?.total_excluded ?? (typeof l?.get_price_without_tax === "function" ? l.get_price_without_tax() : undefined));

                let price_subtotal;
                if (raw_price_without_discount) {
                    // If the exported shape contains a unit-level `price_without_discount`
                    // alongside `unitPrice`, treat it as a unit price and multiply by qty.
                    if (l?.unitPrice || l?.unit_price || l?.price_unit) {
                        price_subtotal = raw_price_without_discount * qty;
                    } else {
                        // Otherwise assume it's the line-level net price already.
                        price_subtotal = raw_price_without_discount;
                    }
                } else {
                    price_subtotal = (price_subtotal_incl / (1.0 + (getLineRate(l) / 100.0)));
                }

            const product_name =
                l?.productName ??
                l?.full_product_name ?? l?.product?.display_name ?? l?.product_id?.name ??
                l?.product_id?.display_name ?? l?.product?.name ?? l?.name ?? "";

            const tax_ids = l?.tax_ids ?? l?.taxes ?? l?.tax_id ?? l?.taxes_ids ?? [];

            return {
                id: l?.id ?? idx,
                qty,
                price_unit,
                price_subtotal,
                price_subtotal_incl,
                product_id: { name: product_name },
                name: product_name,
                tax_ids,
                taxes: l?.taxes,
                tax_label: l?.tax_label,
                taxGroupLabels: l?.taxGroupLabels,
                prices: l?.prices,
                total_included: l?.total_included,
                total_excluded: l?.total_excluded,
            };
        });

        // Log normalized shape for debugging
        try {
            console.debug('[kassa_pos] normalized orderlines length', normalized.length, 'first:', normalized[0]);
        } catch (e) {
            console.warn('[kassa_pos] failed to log normalized orderlines', e);
        }

        return normalized;
    },

    gksLineRate(line) {
        return getLineRate(line);
    },

    gksLineIndicator(line) {
        return this.gksLineRate(line) === 6 ? "F: 6%" : "D: 21%";
    },

    gksLineName(line) {
        return (
            line?.productName ||
            line?.full_product_name ||
            line?.product_id?.name ||
            line?.product_id?.display_name ||
            line?.name ||
            ""
        );
    },

    gksLineQty(line) {
        return toNumber(line?.qty);
    },

    gksLineGross(line) {
        return getLineGross(line);
    },

    gksLineNet(line) {
        return getLineNet(line);
    },

    gksLineVatAmount(line) {
        return getLineVatAmount(line);
    },

    get gksTaxBreakdown() {
        // Prefer server-provided breakdown when available (either injected
        // into the printed `data` or fetched via RPC and cached).
        const serverBreakdown = this.props?.data?.gks_vat_breakdown || this._gksServerBreakdown;
        if (serverBreakdown && serverBreakdown.rates) {
            // Normalize server structure to the shape used by the template
            const rates = {
                6: {
                    net: parseFloat(serverBreakdown.rates[6]?.net || 0),
                    vat: parseFloat(serverBreakdown.rates[6]?.vat || 0),
                    gross: parseFloat(serverBreakdown.rates[6]?.gross || 0),
                },
                21: {
                    net: parseFloat(serverBreakdown.rates[21]?.net || 0),
                    vat: parseFloat(serverBreakdown.rates[21]?.vat || 0),
                    gross: parseFloat(serverBreakdown.rates[21]?.gross || 0),
                },
            };
            return {
                rates,
                netTotal: parseFloat(serverBreakdown.net_total || serverBreakdown.netTotal || 0),
                vatTotal: parseFloat(serverBreakdown.vat_total || serverBreakdown.vatTotal || 0),
                grossTotal: parseFloat(serverBreakdown.gross_total || serverBreakdown.grossTotal || 0),
            };
        }

        // Fallback: compute from local (possibly exported) lines
        const breakdown = {
            6: { net: 0, vat: 0 },
            21: { net: 0, vat: 0 },
        };

        const lines = this.gksReceiptLines || [];
        for (const line of lines) {
            const rate = this.gksLineRate(line);
            const key = rate === 6 ? 6 : 21;
            const net = this.gksLineNet(line);
            const vat = this.gksLineVatAmount(line);
            breakdown[key].net += net;
            breakdown[key].vat += vat;
        }

        return {
            rates: breakdown,
            netTotal: breakdown[6].net + breakdown[21].net,
            vatTotal: breakdown[6].vat + breakdown[21].vat,
            grossTotal: breakdown[6].net + breakdown[21].net + breakdown[6].vat + breakdown[21].vat,
        };
    },

    gksFormatCurrency(amount) {
        // Use POS environment currency formatter if available
        if (this.env?.pos?.formatCurrency) {
            return this.env.pos.formatCurrency(amount || 0);
        }
        // Fallback to manual formatting
        return "€ " + ((amount || 0).toFixed(2)).replace(".", ",");
    },
});
