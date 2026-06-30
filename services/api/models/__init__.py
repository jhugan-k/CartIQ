"""Import every model so Alembic's autogenerate sees all tables.

Importing this package registers User, WishlistItem and CartHistory on Base's
metadata. Alembic's env.py imports `models`, which triggers these imports.
"""

from models.cart_history import CartHistory
from models.user import User
from models.wishlist import WishlistItem

__all__ = ["User", "WishlistItem", "CartHistory"] #defines what is allowed to be imported when using 'from models import *'
