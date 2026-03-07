from app import db
from datetime import datetime
import json


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    input_type = db.Column(db.String(20), nullable=False)  # image/text/link
    raw_input = db.Column(db.Text)
    extracted_product = db.Column(db.Text)
    price_research = db.Column(db.Text)
    sourcing_results = db.Column(db.Text)
    arbitrage_result = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending/processing/complete/error
    error_message = db.Column(db.Text, nullable=True)
    trend_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def _parse(self, field):
        try:
            if field:
                return json.loads(field)
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def get_extracted(self):
        return self._parse(self.extracted_product)

    def get_pricing(self):
        return self._parse(self.price_research)

    def get_sourcing(self):
        return self._parse(self.sourcing_results)

    def get_arbitrage(self):
        return self._parse(self.arbitrage_result)

    def get_trend(self):
        return self._parse(self.trend_data)

    def get_roi_value(self):
        arb = self.get_arbitrage()
        try:
            return float(arb.get('roi_percent', 0))
        except (ValueError, TypeError):
            return 0.0

    def get_roi_class(self):
        roi = self.get_roi_value()
        if roi >= 100:
            return 'success'
        elif roi >= 50:
            return 'warning'
        return 'danger'

    def get_product_summary(self):
        extracted = self.get_extracted()
        brand = extracted.get('brand', '')
        ptype = extracted.get('product_type', '')
        model = extracted.get('model', '')
        parts = [p for p in [brand, ptype, model] if p]
        if parts:
            return ' '.join(parts)
        if self.raw_input:
            return self.raw_input[:80]
        return 'Unknown Product'

    def __repr__(self):
        return f'<Analysis {self.id} {self.status}>'
