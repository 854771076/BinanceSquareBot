from pydantic import BaseModel
from binance_square_bot.config import MainConfig, ModelsRegistry

def test_source_config_registration():
    """Test source config can be registered."""
    class TestSourceConfig(BaseModel):
        enabled: bool = True

    MainConfig.register_source_config("TestSource", TestSourceConfig)
    assert "TestSource" in MainConfig._source_configs

def test_target_config_registration():
    """Test target config can be registered."""
    class TestTargetConfig(BaseModel):
        enabled: bool = True

    MainConfig.register_target_config("TestTarget", TestTargetConfig)
    assert "TestTarget" in MainConfig._target_configs

def test_models_registry():
    """Test models registry works."""
    class TestModel(BaseModel):
        name: str

    ModelsRegistry.register("TestModel", TestModel)
    assert ModelsRegistry.get("TestModel") == TestModel

def test_get_config_class():
    """Test we can retrieve registered config classes."""
    class SampleConfig(BaseModel):
        field: str = "value"

    MainConfig.register_source_config("SampleSource", SampleConfig)
    assert MainConfig.get_source_config_class("SampleSource") == SampleConfig
