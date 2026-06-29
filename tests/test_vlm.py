"""Fake-backed tests for the local Qwen2-VL caption backend."""

from __future__ import annotations

import time

import pytest

from minnarone.video import VideoFrame


class _FakeImage:
    def __init__(self, source):
        self.source = source
        self.converted_to: str | None = None

    def convert(self, mode):
        self.converted_to = mode
        return self


class _FakeImageModule:
    class Image:
        pass

    def __init__(self) -> None:
        self.fromarray_calls = []

    def fromarray(self, pixels):
        self.fromarray_calls.append(pixels)
        return _FakeImage(pixels)


class _FakeTensorList(list):
    def to(self, device):
        self.device = device
        return self


class _FakeInputs(dict):
    def __init__(self):
        super().__init__(input_ids=[_FakeTensorList([1, 2])])
        self.input_ids = self["input_ids"]
        self.moved_to = None

    def to(self, device):
        self.moved_to = device
        return self


class _FakeProcessor:
    def __init__(self):
        self.templates = []
        self.calls = []
        self.decode_calls = []
        self.inputs = _FakeInputs()

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        self.templates.append(
            {
                "messages": messages,
                "tokenize": tokenize,
                "add_generation_prompt": add_generation_prompt,
            }
        )
        return "<prompt>"

    def __call__(self, *, text, images, padding, return_tensors):
        self.calls.append(
            {
                "text": text,
                "images": images,
                "padding": padding,
                "return_tensors": return_tensors,
            }
        )
        return self.inputs

    def batch_decode(
        self,
        generated_ids,
        *,
        skip_special_tokens,
        clean_up_tokenization_spaces,
    ):
        self.decode_calls.append(
            {
                "generated_ids": generated_ids,
                "skip_special_tokens": skip_special_tokens,
                "clean_up_tokenization_spaces": clean_up_tokenization_spaces,
            }
        )
        return ["  A streamer is playing a game on a Twitch overlay.  "]


class _FakeModel:
    device = "cpu"

    def __init__(self):
        self.eval_called = False
        self.generate_calls = []
        self.to_calls = []

    def to(self, device):
        self.to_calls.append(device)
        self.device = device
        return self

    def eval(self):
        self.eval_called = True

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return [_FakeTensorList([1, 2, 99, 100])]


class _NoGrad:
    def __enter__(self):
        return None

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class _FakeTorch:
    def no_grad(self):
        return _NoGrad()


def test_qwen_captioner_uses_local_model_processor_and_in_memory_image():
    from minnarone.vlm import Qwen2VlCaptioner, QwenVlConfig

    image_module = _FakeImageModule()
    processor = _FakeProcessor()
    model = _FakeModel()
    constructed = {}

    def model_factory(model_id, **kwargs):
        constructed["model"] = model_id
        constructed["kwargs"] = kwargs
        return model

    def processor_factory(model_id):
        constructed["processor"] = model_id
        return processor

    captioner = Qwen2VlCaptioner(
        QwenVlConfig(
            model="/models/qwen2-vl",
            device="cpu",
            torch_dtype="auto",
            attn_implementation="sdpa",
            max_new_tokens=24,
        ),
        model_factory=model_factory,
        processor_factory=processor_factory,
        torch_module=_FakeTorch(),
        image_module=image_module,
    )

    text = captioner.caption(VideoFrame(pixels=["rgb"], ts=7.0))

    assert text == "A streamer is playing a game on a Twitch overlay."
    assert constructed == {
        "model": "/models/qwen2-vl",
        "processor": "/models/qwen2-vl",
        "kwargs": {"torch_dtype": "auto", "attn_implementation": "sdpa"},
    }
    assert model.eval_called is True
    assert model.to_calls == ["cpu"]
    assert image_module.fromarray_calls == [["rgb"]]
    template = processor.templates[0]
    assert template["tokenize"] is False
    assert template["add_generation_prompt"] is True
    prompt_content = template["messages"][0]["content"]
    image = processor.calls[0]["images"][0]
    assert prompt_content[0]["type"] == "image"
    assert prompt_content[0]["image"] is image
    assert image.source == ["rgb"]
    assert image.converted_to == "RGB"
    assert "concise English" in prompt_content[1]["text"]
    assert processor.calls == [
        {
            "text": ["<prompt>"],
            "images": [processor.calls[0]["images"][0]],
            "padding": True,
            "return_tensors": "pt",
        }
    ]
    assert processor.inputs.moved_to == "cpu"
    assert model.generate_calls[0]["max_new_tokens"] == 24
    assert model.generate_calls[0]["do_sample"] is False
    assert processor.decode_calls == [
        {
            "generated_ids": [[99, 100]],
            "skip_special_tokens": True,
            "clean_up_tokenization_spaces": False,
        }
    ]


def test_qwen_captioner_requires_model_for_real_backend():
    from minnarone.vlm import Qwen2VlCaptioner, QwenVlCaptionError, QwenVlConfig

    with pytest.raises(QwenVlCaptionError, match="vlm.model"):
        Qwen2VlCaptioner(QwenVlConfig(model=None))


def test_qwen_config_rejects_custom_device_map_with_explicit_device():
    from minnarone.vlm import QwenVlConfig, QwenVlConfigError

    with pytest.raises(QwenVlConfigError, match="device_map"):
        QwenVlConfig(model="local", device="cpu", device_map="balanced")


def test_qwen_config_language_changes_default_prompt():
    from minnarone.vlm import QwenVlConfig

    config = QwenVlConfig(language="it")

    assert "concise Italian sentence" in config.prompt


def test_qwen_captioner_times_out_without_killing_caller():
    from minnarone.vlm import Qwen2VlCaptioner, QwenVlCaptionError, QwenVlConfig

    class BlockingModel(_FakeModel):
        def generate(self, **kwargs):
            time.sleep(0.2)
            return super().generate(**kwargs)

    captioner = Qwen2VlCaptioner(
        QwenVlConfig(model="local", timeout_seconds=0.01),
        model_factory=lambda _model_id, **_kwargs: BlockingModel(),
        processor_factory=lambda _model_id: _FakeProcessor(),
        torch_module=_FakeTorch(),
        image_module=_FakeImageModule(),
    )

    with pytest.raises(QwenVlCaptionError, match="timed out"):
        captioner.caption(VideoFrame(pixels=["rgb"]))


def test_qwen_captioner_does_not_overlap_after_timeout():
    from minnarone.vlm import Qwen2VlCaptioner, QwenVlCaptionError, QwenVlConfig

    class BlockingModel(_FakeModel):
        calls = 0

        def generate(self, **kwargs):
            type(self).calls += 1
            time.sleep(0.2)
            return super().generate(**kwargs)

    captioner = Qwen2VlCaptioner(
        QwenVlConfig(model="local", timeout_seconds=0.01),
        model_factory=lambda _model_id, **_kwargs: BlockingModel(),
        processor_factory=lambda _model_id: _FakeProcessor(),
        torch_module=_FakeTorch(),
        image_module=_FakeImageModule(),
    )

    with pytest.raises(QwenVlCaptionError, match="timed out"):
        captioner.caption(VideoFrame(pixels=["rgb"]))
    with pytest.raises(QwenVlCaptionError, match="still busy"):
        captioner.caption(VideoFrame(pixels=["rgb-2"]))
    assert BlockingModel.calls == 1


def test_frame_to_image_accepts_existing_image_without_writing_files():
    from minnarone.vlm import frame_to_pil_image

    image = _FakeImage("already-image")

    converted = frame_to_pil_image(VideoFrame(pixels=image), image_module=_FakeImageModule())

    assert converted is image
    assert image.converted_to == "RGB"
