/** @odoo-module **/

import { useService } from '@web/core/utils/hooks';
import { Component } from '@odoo/owl';
import { sprintf } from '@web/core/utils/strings';

export class ClosingButton extends Component {
    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
    }

    async onClosingClick() {
        try {
            // Call the close_daily_batch method
            const result = await this.orm.call(
                'pos.order',
                'close_daily_batch',
                [],
                {}
            );

            if (result.success) {
                // Success notification
                this.notification.add(
                    result.message,
                    {
                        title: 'POS Batch Closed',
                        type: 'success',
                    }
                );

                // Log batch details
                console.log('Batch Details:', {
                    batchId: result.batch_id,
                    ordersCount: result.orders_count,
                    totalAmount: result.total_amount
                });

                // Optional: trigger UI update or navigate
                if (result.batch_id) {
                    this._showBatchDetails(result);
                }
            } else {
                // Error notification
                this.notification.add(
                    result.message,
                    {
                        title: 'Error Closing Batch',
                        type: 'danger',
                    }
                );
            }
        } catch (error) {
            console.error('Error closing batch:', error);
            this.notification.add(
                `Failed to close batch: ${error.message}`,
                {
                    title: 'System Error',
                    type: 'danger',
                }
            );
        }
    }

    _showBatchDetails(result) {
        const message = sprintf(
            'Batch %s\nOrders: %d\nTotal: €%.2f',
            result.batch_id,
            result.orders_count,
            result.total_amount
        );

        console.log('Batch closed successfully:', message);
    }

    static template = 'kassa_pos.ClosingButton';
}

// Template definition for OWL
import { xml } from '@odoo/owl';

ClosingButton.template = xml`
    <div class="closing-button-container">
        <button class="btn btn-lg kassa-closing-button-outline closing-button" t-on-click="onClosingClick" title="Close daily session and send batch to facturatie">
            <i class="fa fa-save"></i>
            Afsluiten &amp; Batch Verzenden
        </button>
    </div>
`;

