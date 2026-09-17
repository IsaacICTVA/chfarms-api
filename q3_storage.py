"""Durable Q3 operational records. PostgreSQL is required in production."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = db.Column(db.String(40), nullable=False)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.String(36), nullable=False)
    actor = db.Column(db.String(80), nullable=False)
    reason = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)


class BatchArrival(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_code = db.Column(db.String(40), unique=True, nullable=False)
    arrival_date = db.Column(db.Date, nullable=False)
    supplier = db.Column(db.String(120), nullable=False)
    doc_count = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    feed_type = db.Column(db.String(80), nullable=False)
    house = db.Column(db.String(80))
    status = db.Column(db.String(24), default="active", nullable=False)
    created_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)


class FeedRecord(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_date = db.Column(db.Date, nullable=False)
    movement_type = db.Column(db.String(12), nullable=False)  # supply or usage
    feed_type = db.Column(db.String(80), nullable=False)
    quantity_bags = db.Column(db.Numeric(10, 2), nullable=False)
    batch_code = db.Column(db.String(40))
    house = db.Column(db.String(80))
    supplier = db.Column(db.String(120))
    unit_cost = db.Column(db.Numeric(12, 2))
    reference = db.Column(db.String(120))
    notes = db.Column(db.String(500))
    created_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)


class ProcessingSession(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    processing_date = db.Column(db.Date, nullable=False)
    source_batch = db.Column(db.String(80), nullable=False)
    birds_received = db.Column(db.Integer, nullable=False)
    birds_processed = db.Column(db.Integer, nullable=False)
    birds_rejected = db.Column(db.Integer, default=0, nullable=False)
    live_weight_kg = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    labor_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    transport_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    utilities_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    packaging_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    inspection_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    other_cost = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    status = db.Column(db.String(24), default="draft", nullable=False)
    created_by = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    items = db.relationship("ProcessingItem", backref="session", cascade="all, delete-orphan")

    @property
    def expense_total(self):
        return sum(float(value or 0) for value in (self.labor_cost, self.transport_cost, self.utilities_cost, self.packaging_cost, self.inspection_cost, self.other_cost))


class ProcessingItem(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("processing_session.id"), nullable=False)
    product = db.Column(db.String(80), nullable=False)  # whole chicken, breast, liver, gizzard, etc.
    category = db.Column(db.String(24), nullable=False)  # whole, part, evisceral
    weight_kg = db.Column(db.Numeric(12, 2), nullable=False)
    pack_count = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    unit = db.Column(db.String(24), default="kg", nullable=False)
    selling_rate = db.Column(db.Numeric(12, 2), nullable=False)

    @property
    def sale_value(self):
        return float(self.weight_kg) * float(self.selling_rate)
