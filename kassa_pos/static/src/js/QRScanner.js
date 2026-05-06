/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, xml } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { Dialog } from '@web/core/dialog/dialog';
import { ProductScreen } from '@point_of_sale/app/screens/product_screen/product_screen';


// ── Camera Scanner Dialog ──────────────────────────────────────────────────────

class QRScannerDialog extends Component {
    static components = { Dialog };
    static props = ['close'];
    static template = xml`
        <Dialog title="'QR-code Scanner'" class="kassa-scanner-dialog">
            <div class="kassa-scanner-body">

                <t t-if="state.found">
                    <div class="kassa-scanner-success">
                        <i class="fa fa-check-circle fa-3x text-success"/>
                        <p class="kassa-scanner-name"><t t-esc="state.partnerName"/></p>
                        <p class="text-muted">Klant is ingesteld op de bestelling.</p>
                        <button class="button btn-primary" t-on-click="props.close">Sluiten</button>
                    </div>
                </t>

                <t t-elif="state.error">
                    <div class="kassa-scanner-error">
                        <i class="fa fa-exclamation-circle fa-2x text-danger"/>
                        <p><t t-esc="state.error"/></p>
                        <button class="button btn-secondary" t-on-click="props.close">Sluiten</button>
                    </div>
                </t>

                <t t-else="">
                    <p class="text-muted kassa-scanner-hint">Houd de QR-code voor de camera.</p>
                    <video t-ref="video" class="kassa-scanner-video" autoplay="autoplay" playsinline="playsinline"/>
                </t>

            </div>
        </Dialog>
    `;

    setup() {
        this.pos = useService('pos');
        this.orm = useService('orm');
        this.notification = useService('notification');

        this.state = useState({
            found: false,
            partnerName: '',
            error: '',
        });

        this.videoRef = useRef('video');
        this.stream = null;
        this.animFrameId = null;
        this.detector = null;

        onMounted(() => this._startCamera());
        onWillUnmount(() => this._stopCamera());
    }

    async _startCamera() {
        if (!('BarcodeDetector' in window)) {
            this.state.error = 'BarcodeDetector wordt niet ondersteund in deze browser. Gebruik Chrome of Edge.';
            return;
        }

        try {
            this.detector = new BarcodeDetector({ formats: ['qr_code'] });
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' },
            });
            const video = this.videoRef.el;
            video.srcObject = this.stream;
            await video.play();
            this._scanLoop();
        } catch (e) {
            this.state.error = 'Camera niet beschikbaar: ' + e.message;
        }
    }

    _stopCamera() {
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
    }

    _scanLoop() {
        if (this.state.found || this.state.error) return;

        const video = this.videoRef.el;
        if (!video || video.readyState < 2) {
            this.animFrameId = requestAnimationFrame(() => this._scanLoop());
            return;
        }

        this.detector.detect(video).then(barcodes => {
            if (barcodes.length > 0) {
                this._handleCode(barcodes[0].rawValue);
            } else {
                this.animFrameId = requestAnimationFrame(() => this._scanLoop());
            }
        }).catch(() => {
            this.animFrameId = requestAnimationFrame(() => this._scanLoop());
        });
    }

    async _handleCode(code) {
        this._stopCamera();

        // Zoek eerst in lokale POS database
        const partners = this.pos.db.get_partners_sorted();
        let partner = partners.find(p => p.badge_code === code);

        // Niet lokaal gevonden — zoek via RPC
        if (!partner) {
            try {
                const results = await this.orm.searchRead(
                    'res.partner',
                    [['badge_code', '=', code]],
                    ['id', 'name', 'email', 'phone', 'badge_code', 'role', 'company_id_custom', 'user_id_custom'],
                    { limit: 1 },
                );
                if (results.length > 0) {
                    this.pos.db.add_partners(results);
                    partner = results[0];
                }
            } catch (e) {
                this.state.error = 'Fout bij opzoeken klant: ' + e.message;
                return;
            }
        }

        if (partner) {
            const order = this.pos.get_order();
            if (order) {
                order.set_partner(partner);
            }
            this.state.found = true;
            this.state.partnerName = partner.name;
        } else {
            this.state.error = `Geen klant gevonden voor gescande code.`;
        }
    }
}


// ── Scanner Button (ProductScreen) ────────────────────────────────────────────

class QRScannerButton extends Component {
    static template = xml`
        <button class="button kassa-scanner-btn" t-on-click="onScannerClick" title="Scan QR-code van klant">
            <i class="fa fa-camera"/>
            <span>Scanner</span>
        </button>
    `;

    setup() {
        this.dialog = useService('dialog');
    }

    onScannerClick() {
        this.dialog.add(QRScannerDialog, {});
    }
}

ProductScreen.addControlButton({
    component: QRScannerButton,
    condition: () => true,
});
