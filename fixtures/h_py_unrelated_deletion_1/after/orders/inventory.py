'''On-hand and reserved units for the warehouse desk.'''

from __future__ import annotations

import threading


class StockError(Exception):
    '''A reservation or receipt could not be applied.'''


class Stock:
    '''Track on-hand and reserved units for each SKU.

    Each mutating method takes the lock itself. Callers do not hold it,
    and one Stock instance is not shared across desks.
    '''

    def __init__(self) -> None:
        self._on_hand: dict[str, int] = {}
        self._reserved: dict[str, int] = {}
        self._lock = threading.Lock()

    def receive(self, sku: str, quantity: int) -> None:
        '''Add received units to on-hand stock.'''
        if quantity <= 0:
            raise StockError(f'{sku} quantity must be positive')
        with self._lock:
            self._on_hand[sku] = self._on_hand.get(sku, 0) + quantity

    def reserve(self, sku: str, quantity: int) -> None:
        '''Hold units for a submitted or replaced line.'''
        if quantity <= 0:
            raise StockError(f'{sku} quantity must be positive')
        with self._lock:
            available = self._on_hand.get(sku, 0) - self._reserved.get(sku, 0)
            if quantity > available:
                raise StockError(f'{sku} short by {quantity - available}')
            self._reserved[sku] = self._reserved.get(sku, 0) + quantity

    def release(self, sku: str, quantity: int) -> None:
        '''Return reserved units. On-hand stock is left unchanged.'''
        if quantity <= 0:
            raise StockError(f'{sku} quantity must be positive')
        with self._lock:
            reserved = self._reserved.get(sku, 0)
            self._reserved[sku] = max(0, reserved - quantity)

    def available(self, sku: str) -> int:
        '''Units that can still be reserved.'''
        with self._lock:
            return self._on_hand.get(sku, 0) - self._reserved.get(sku, 0)
