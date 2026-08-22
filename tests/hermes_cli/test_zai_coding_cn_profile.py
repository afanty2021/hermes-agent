"""zai-coding-cn profile 注册回归测试（评审发现 B）。

背景：``hermes model zai-coding-cn`` 的交互 dispatch 走 main.py 的
``_is_profile_api_key_provider`` catch-all（按 profile 注册表判定）。
该名字此前只在 auth.PROVIDER_REGISTRY / hermes_cli.providers overlay，
profile 注册表无条目 → catch-all 返回 False → 交互切换静默落空。
上游 set 重构 merge 吞条目是本 fork 已实证两次的模式（computer_use
never-parallel / zai-coding-cn dispatch），此测试是第二次的回归锚。
"""

from __future__ import annotations


class TestZaiCodingCnProfile:
    def test_profile_registered_as_api_key(self):
        """get_provider_profile('zai-coding-cn') 非 None 且 auth_type=api_key。

        这是 main.py catch-all dispatch 的判定条件——缺失即回到发现 B
        的静默落空。
        """
        from providers import get_provider_profile

        profile = get_provider_profile("zai-coding-cn")
        assert profile is not None, (
            "zai-coding-cn profile 未注册——hermes model 交互切换会静默落空"
            "（评审发现 B；check plugins/model-providers/zai/__init__.py 的 fork 追加块）"
        )
        assert profile.auth_type == "api_key"

    def test_dispatch_catchall_covers_zai_coding_cn(self):
        """main.py 的 _is_profile_api_key_provider('zai-coding-cn') 必须为 True。

        直接测 dispatch 判定函数（不 import 整个 main 的交互流），与
        test_tool_batch_segmentation 的 computer_use 回归测试同型——
        锚定"上游 merge 静默吞条目"模式。
        """
        from hermes_cli.main import _is_profile_api_key_provider

        assert _is_profile_api_key_provider("zai-coding-cn") is True

    def test_inherits_zai_thinking_behavior(self):
        """子类化 ZaiProfile：thinking 关闭偏好必须翻译成 extra_body。

        live（lt-tutor, glm-5.2 @ coding-cn 端点）依赖 thinking disabled——
        若注册退化为裸 ProviderProfile 会静默回到 thinking 默认开。
        """
        from providers import get_provider_profile

        profile = get_provider_profile("zai-coding-cn")
        extra_body, top_level = profile.build_api_kwargs_extras(
            reasoning_config={"enabled": False}, model="glm-5.2"
        )
        assert extra_body.get("thinking") == {"type": "disabled"}

    def test_base_url_points_to_cn_coding_endpoint(self):
        """默认 base_url 是国内 Coding Plan 端点（与 auth.ZAI_ENDPOINTS 的
        coding-cn 条目一致——探测与 profile 默认值不能漂移成两个端点）。"""
        from providers import get_provider_profile
        from hermes_cli.auth import ZAI_ENDPOINTS

        profile = get_provider_profile("zai-coding-cn")
        coding_cn = next(e for e in ZAI_ENDPOINTS if e[0] == "coding-cn")
        assert profile.base_url == coding_cn[1]
