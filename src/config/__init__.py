# Config Package
"""
Configuration files for the Alert Decision Agent.

- defaults.yaml: Default settings for all components
- rules_engine.yaml: Deterministic rule definitions

Usage:
    import yaml
    from pathlib import Path
    
    config_dir = Path(__file__).parent
    with open(config_dir / "defaults.yaml") as f:
        config = yaml.safe_load(f)
"""

from pathlib import Path

CONFIG_DIR = Path(__file__).parent

__all__ = ["CONFIG_DIR"]
