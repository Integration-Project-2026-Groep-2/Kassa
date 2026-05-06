/** @odoo-module **/

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
    return toNumber(
        parseCurrency(line?.price) ??  // export_for_printing format: "8.40 €"
            line?.price_subtotal_incl ??
            line?.prices?.total_included ??
            line?.total_included ??
            line?.price_unit * toNumber(line?.qty)
    );
}

function getLineNet(line) {
    const gross = getLineGross(line);
    const rate = getLineRate(line);
    return gross / (1.0 + (rate / 100.0));
}

function getLineVatAmount(line) {
    const gross = getLineGross(line);
    const net = getLineNet(line);
    const vat = gross - net;
    return Number.isFinite(vat) ? vat : 0;
}

patch(OrderReceipt.prototype, {
    get gksCompanyName() {
        return "Desiderius Hogeschool";
    },

    get gksCompanyAddress() {
        return "Straatnaam 1, 1000 Brussel";
    },

    get gksVatNumber() {
        return "BE 0123.456.789";
    },

    get gksReceiptLines() {
        let order = this.order || this.props?.order;

        // If order not available on the component, try the `data` prop (export_for_printing())
        const printedData = this.props?.data;
        if (!order && printedData) {
            console.debug('[kassa_pos] gksReceiptLines - using props.data');
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

        const normalized = (raw || []).map((l, idx) => {
            const qty = toNumber(
                l?.quantity ?? l?.qty ?? l?.qty_order ??
                parseCurrency(l?.qty) ?? // export_for_printing() has qty as string like "3.00"
                (typeof l?.get_quantity === "function" ? l.get_quantity() : undefined) ?? 0
            );

            const price_unit = toNumber(
                l?.price_unit ??
                parseCurrency(l?.unitPrice) ?? // export_for_printing format
                l?.unit_price ?? l?.price ??
                (typeof l?.get_unit_price === "function" ? l.get_unit_price() : undefined) ?? 0
            );

            const price_subtotal_incl = toNumber(
                parseCurrency(l?.price) ??  // export_for_printing format: "8.40 €"
                    l?.price_subtotal_incl ?? l?.prices?.total_included ?? l?.total_included ??
                    (typeof l?.get_price_included === "function" ? l.get_price_included() : undefined) ??
                    price_unit * qty
            );

            // Assume net = gross / (1 + tax rate)
            const price_subtotal = toNumber(
                l?.price_subtotal ?? l?.prices?.total_excluded ?? l?.total_excluded ??
                    (typeof l?.get_price_without_tax === "function" ? l.get_price_without_tax() : undefined) ??
                    price_subtotal_incl / 1.21  // fallback: assume 21% tax
            );

            const product_name =
                l?.productName ??  // export_for_printing format
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
