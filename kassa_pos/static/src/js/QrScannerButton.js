/** @odoo-module **/

import { Component, onWillUnmount, useRef, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";

/**
 * Laad jsQR éénmalig als gewone <script> tag — werkt op alle browsers
 * inclusief desktop Chrome/Windows (BarcodeDetector werkt daar niet).
 */
function loadJsQR() {
    if (window.jsQR) return Promise.resolve(window.jsQR);
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/kassa_pos/static/src/lib/jsQR.min.js";
        script.onload = () => resolve(window.jsQR);
        script.onerror = () => reject(new Error("jsQR kon niet geladen worden"));
        document.head.appendChild(script);
    });
}

/**
 * QR Scanner Dialog
 * Opent de camera en scant QR-codes via jsQR + canvas.
 * Zodra een geldige klant herkend wordt via badge_code,
 * wordt die onmiddellijk ingesteld op de bestelling.
 */
class QrScannerDialog extends Component {
    static components = { Dialog };

    static template = xml`
        <Dialog title="'QR-code Scanner'" class="kassa-scanner-dialog">
            <div class="kassa-scanner-body">
                <div t-if="state.error" class="kassa-scanner-error">
                    <i class="fa fa-exclamation-triangle me-2"/>
                    <t t-esc="state.error"/>
                </div>
                <div t-if="!state.error" class="kassa-scanner-video-wrapper">
                    <video t-ref="video" class="kassa-scanner-video" autoplay="1" playsinline="1"/>
                    <div class="kassa-scanner-overlay">
                        <div class="kassa-scanner-frame"/>
                        <span class="kassa-scanner-hint">Richt de camera op een QR-code</span>
                    </div>
                </div>
                <div t-if="state.foundName" class="kassa-scanner-found">
                    <i class="fa fa-check-circle me-2"/>
                    Klant geselecteerd: <strong><t t-esc="state.foundName"/></strong>
                </div>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="close">Sluiten</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.videoRef = useRef("video");

        this.state = useState({
            error: "",
            foundName: "",
        });

        this._stream = null;
        this._rafId = null;
        this._canvas = null;
        this._scanning = true;

        this._startCamera();
        onWillUnmount(() => this._stopCamera());
    }

    async _startCamera() {
        // jsQR laden (wordt gecachet na eerste keer)
        try {
            await loadJsQR();
        } catch (e) {
            this.state.error = _t("QR-bibliotheek kon niet geladen worden: ") + e.message;
            return;
        }

        // Camera openen
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" },
            });
        } catch {
            try {
                this._stream = await navigator.mediaDevices.getUserMedia({ video: true });
            } catch (e) {
                this.state.error = _t("Camera toegang geweigerd: ") + e.message;
                return;
            }
        }

        const video = this.videoRef.el;
        if (!video) return;

        video.srcObject = this._stream;
        this._canvas = document.createElement("canvas");

        video.addEventListener("loadedmetadata", () => this._scanLoop());
    }

    _scanLoop() {
        if (!this._scanning) return;

        const video = this.videoRef.el;
        if (!video || video.readyState < 2 || !video.videoWidth) {
            this._rafId = requestAnimationFrame(() => this._scanLoop());
            return;
        }

        // Frame naar canvas tekenen en QR decoderen
        const canvas = this._canvas;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

        const code = window.jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert",
        });

        if (code && this._scanning) {
            this._onQrDetected(code.data);
        } else {
            this._rafId = requestAnimationFrame(() => this._scanLoop());
        }
    }

    async _onQrDetected(token) {
        this._scanning = false;

        const partner = await this._findPartnerByBadgeCode(token);

        if (partner) {
            const currentOrder = this.pos.get_order();
            if (currentOrder) {
                currentOrder.set_partner(partner);
            }
            this.state.foundName = partner.name;
            this.notification.add(_t("Klant geselecteerd: ") + partner.name, { type: "success" });
            setTimeout(() => this.close(), 900);
        } else {
            this.notification.add(
                _t("Geen klant gevonden voor deze QR-code."),
                { type: "warning" }
            );
            setTimeout(() => {
                this._scanning = true;
                this._scanLoop();
            }, 1500);
        }
    }

    async _findPartnerByBadgeCode(badgeCode) {
        // Eerst lokale POS-cache (snel)
        const partners = this.pos.db.get_partners_sorted();
        const local = partners.find((p) => p.badge_code === badgeCode);
        if (local) return local;

        // Dan via RPC
        try {
            const result = await this.orm.searchRead(
                // note(nasr): the badge id thing is an internal id that doesnt map to the crm id so this should fix it
                // so copilot says
                "res.partner",
                [["user_id_custom", "=", badgeCode]],
                [["badge_code", "=", badgeCode]],
                ["id", "name", "email", "phone", "badge_code", "role", "company_id_custom", "user_id_custom"],
                { limit: 1 }
            );
            if (result && result.length > 0) {
                this.pos.db.add_partners(result);
                return result[0];
            }
        } catch (e) {
            console.error("Fout bij badge-opzoeking:", e);
        }

        return null;
    }

    _stopCamera() {
        this._scanning = false;
        if (this._rafId) cancelAnimationFrame(this._rafId);
        if (this._stream) {
            this._stream.getTracks().forEach((t) => t.stop());
            this._stream = null;
        }
    }

    close() {
        this._stopCamera();
        if (this.props.close) this.props.close();
    }
}

class QrScannerButton extends Component {
    static template = xml`
        <button
            class="button kassa-pos-control-btn kassa-pos-control-btn--slate kassa-scanner-btn"
            t-on-click="openScanner"
            title="QR-code scanner"
        >
            <i class="fa fa-camera"/>
            <span>Scanner</span>
        </button>
    `;

    setup() {
        this.dialog = useService("dialog");
    }

    openScanner() {
        this.dialog.add(QrScannerDialog, {});
    }
}

ProductScreen.addControlButton({
    component: QrScannerButton,
    position: ["after", "ClosingButton"],
    condition: () => true,
});
