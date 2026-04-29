/** @odoo-module **/

import { Component, xml } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { sprintf } from '@web/core/utils/strings';
import { ProductScreen } from '@point_of_sale/app/screens/product_screen/product_screen';

class ClosingButton extends Component {
    static template = xml`
        <button class="button kassa-closing-btn" t-on-click="onClosingClick" title="Dagafsluiting versturen naar facturatie">
            <i class="fa fa-save"/>
            <span>Afsluitknop</span>
        </button>
    `;

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
    }

    async onClosingClick() {
        try {
            const result = await this.orm.call('pos.order', 'close_daily_batch', [], {});

            if (result.success) {
                this.notification.add(result.message, {
                    title: 'Dagafsluiting verstuurd',
                    type: 'success',
                });

                if (result.batch_id) {
                    console.log('Batch gesloten:', sprintf(
                        'Batch %s — %d orders — €%.2f',
                        result.batch_id,
                        result.orders_count,
                        result.total_amount
                    ));
                }
            } else {
                this.notification.add(result.message, {
                    title: 'Fout bij dagafsluiting',
                    type: 'danger',
                });
            }
        } catch (error) {
            console.error('Fout bij dagafsluiting:', error);
            this.notification.add(`Fout: ${error.message}`, {
                title: 'Systeemfout',
                type: 'danger',
            });
        }
    }
}

ProductScreen.addControlButton({
    component: ClosingButton,
    condition: function () {
        return true;
    },
});
