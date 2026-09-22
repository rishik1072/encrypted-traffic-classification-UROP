"""
Encrypted Traffic Monitor - Windows Local Productization Package.

Provides local-only, zero-payload encrypted network traffic classification
with Npcap-based adapter discovery, cryptographic model registry validation,
and desktop SOC dashboard visualization.
"""

from product.adapter_manager import get_default_adapter, list_adapters, validate_adapter
from product.app import ProductApplication
from product.config import product_config
from product.environment import check_npcap, get_os_info, is_admin, is_windows
from product.health import run_product_health_check
from product.lifecycle import ProductLifecycleManager
from product.security import validate_security_boundary
from product.version import APP_DESCRIPTION, APP_NAME, __version__

__all__ = [
    "APP_NAME",
    "APP_DESCRIPTION",
    "__version__",
    "ProductApplication",
    "ProductLifecycleManager",
    "product_config",
    "list_adapters",
    "get_default_adapter",
    "validate_adapter",
    "check_npcap",
    "get_os_info",
    "is_admin",
    "is_windows",
    "run_product_health_check",
    "validate_security_boundary",
]
