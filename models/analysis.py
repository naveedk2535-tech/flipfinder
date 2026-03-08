from app import db
from datetime import datetime
import json


CATEGORY_MAP = [
    (['sneaker', 'shoe', 'trainer', 'boot', 'sandal'], ('Sneakers', 'indigo')),
    (['clothing', 'jacket', 'shirt', 'dress', 'hoodie', 'jeans', 'coat', 'top', 'trousers', 'sweatshirt', 'sweater', 'knitwear'], ('Clothing', 'violet')),
    (['handbag', 'bag', 'backpack', 'purse', 'wallet', 'tote', 'clutch'], ('Bags', 'pink')),
    (['watch'], ('Watches', 'amber')),
    (['electronic', 'phone', 'laptop', 'console', 'camera', 'tablet', 'headphone', 'airpod', 'speaker', 'ipad', 'iphone'], ('Electronics', 'cyan')),
    (['card', 'toy', 'figure', 'collectible', 'lego', 'action figure', 'vinyl', 'funko'], ('Collectibles', 'emerald')),
    (['book', 'record', 'dvd', 'cd', 'game', 'video game'], ('Books & Media', 'orange')),
]


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
    social_data = db.Column(db.Text, nullable=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
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

    def get_social(self):
        return self._parse(self.social_data)

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
            return 'good'
        elif roi >= 0:
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

    def get_category(self):
        """Return (label, colour) tuple derived from product_type in extracted_product JSON."""
        extracted = self.get_extracted()
        ptype = extracted.get('product_type', '').lower()
        for keywords, result in CATEGORY_MAP:
            if any(k in ptype for k in keywords):
                return result
        return ('Other', 'slate')

    def __repr__(self):
        return f'<Analysis {self.id} {self.status}>'
