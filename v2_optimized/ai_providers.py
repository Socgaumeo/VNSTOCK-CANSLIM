#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AI PROVIDER MODULE - MULTI VENDOR                         ║
║           Hỗ trợ: Gemini | Claude | DeepSeek | OpenAI | Groq                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cách sử dụng:
    from ai_providers import AIProvider, AIConfig
    
    config = AIConfig(
        provider="deepseek",  # hoặc "gemini", "claude", "openai", "groq"
        api_key="your_api_key"
    )
    
    ai = AIProvider(config)
    response = ai.chat("Phân tích thị trường...")
"""

import os
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class ProviderType(Enum):
    """Các AI Provider được hỗ trợ"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    GROQ = "groq"


@dataclass
class AIConfig:
    """Cấu hình AI Provider"""
    
    # Provider selection
    provider: str = "deepseek"      # gemini | claude | deepseek | openai | groq
    api_key: str = ""
    
    # Model selection (mặc định theo provider)
    model: str = ""
    
    # Generation settings
    max_tokens: int = 4096
    temperature: float = 0.7
    
    # System prompt mặc định
    system_prompt: str = "Bạn là chuyên gia phân tích chứng khoán Việt Nam theo trường phái VSA."

    # Default models per provider
    DEFAULT_MODELS: Dict[str, str] = field(default_factory=lambda: {
        "gemini": "gemini-3-pro-preview",  # Model Pro 3.0 Preview - mới nhất
        "claude": "claude-3-5-sonnet-20241022",
        "deepseek": "deepseek-chat",
        "openai": "gpt-4o-mini",
        "groq": "llama-3.1-70b-versatile"
    })
    
    def get_model(self) -> str:
        """Lấy model name, dùng default nếu không chỉ định"""
        if self.model:
            return self.model
        return self.DEFAULT_MODELS.get(self.provider, "")


# ══════════════════════════════════════════════════════════════════════════════
# BASE PROVIDER (Abstract)
# ══════════════════════════════════════════════════════════════════════════════

class BaseAIProvider(ABC):
    """Base class cho các AI Provider"""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._validate_api_key()
    
    def _validate_api_key(self):
        if not self.config.api_key:
            raise ValueError(f"API key cho {self.config.provider} không được để trống!")
    
    @abstractmethod
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """Gửi prompt và nhận response"""
        pass
    
    @abstractmethod
    def chat_with_history(self, messages: List[Dict]) -> str:
        """Chat với lịch sử hội thoại"""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE GEMINI
# ══════════════════════════════════════════════════════════════════════════════

class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI
    
    API Key: https://makersuite.google.com/app/apikey
    Pricing: Free tier có 60 requests/phút
    """
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._init_client()
    
    def _init_client(self):
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.config.api_key)
            
            # Khởi tạo model với system_instruction (không có generation_config để tránh block)
            self.model = genai.GenerativeModel(
                model_name=self.config.get_model(),
                system_instruction=self.config.system_prompt
            )
            print(f"✓ Gemini initialized: {self.config.get_model()}")
            
        except ImportError:
            raise ImportError("Chạy: pip install google-generativeai")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        try:
            import google.generativeai as genai
            
            # Nếu có system_prompt mới, tạo model mới với system_prompt đó
            if system_prompt:
                model = genai.GenerativeModel(
                    model_name=self.config.get_model(),
                    system_instruction=system_prompt
                )
            else:
                model = self.model
            
            response = model.generate_content(prompt)
            
            # Kiểm tra và xử lý response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    return candidate.content.parts[0].text
                elif candidate.finish_reason:
                    return f"⚠️ Response bị block: finish_reason={candidate.finish_reason}"
            
            return response.text
            
        except Exception as e:
            return f"❌ Lỗi Gemini: {str(e)}"
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        try:
            chat = self.model.start_chat(history=[])
            
            for msg in messages[:-1]:  # Add history except last
                role = "user" if msg["role"] == "user" else "model"
                chat.history.append({"role": role, "parts": [msg["content"]]})
            
            # Send last message
            response = chat.send_message(messages[-1]["content"])
            return response.text
            
        except Exception as e:
            return f"❌ Lỗi Gemini: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# ANTHROPIC CLAUDE
# ══════════════════════════════════════════════════════════════════════════════

class ClaudeProvider(BaseAIProvider):
    """
    Anthropic Claude
    
    API Key: https://console.anthropic.com/
    Pricing: Pay per token
    """
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._init_client()
    
    def _init_client(self):
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.config.api_key)
            print(f"✓ Claude initialized: {self.config.get_model()}")
            
        except ImportError:
            raise ImportError("Chạy: pip install anthropic")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        try:
            response = self.client.messages.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                system=system_prompt or self.config.system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
            
        except Exception as e:
            return f"❌ Lỗi Claude: {str(e)}"
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        try:
            # Extract system from first message if present
            system = self.config.system_prompt
            chat_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    chat_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            response = self.client.messages.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                system=system,
                messages=chat_messages
            )
            return response.content[0].text
            
        except Exception as e:
            return f"❌ Lỗi Claude: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# DEEPSEEK (Giá rẻ nhất, chất lượng tốt)
# ══════════════════════════════════════════════════════════════════════════════

class DeepSeekProvider(BaseAIProvider):
    """
    DeepSeek AI
    
    API Key: https://platform.deepseek.com/
    Pricing: ~$0.14/1M input tokens (RẺ NHẤT)
    
    Ưu điểm: Giá rẻ, hỗ trợ tiếng Việt tốt, API tương thích OpenAI
    """
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            
            self.client = OpenAI(
                api_key=self.config.api_key,
                base_url="https://api.deepseek.com"
            )
            print(f"✓ DeepSeek initialized: {self.config.get_model()}")
            
        except ImportError:
            raise ImportError("Chạy: pip install openai")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt or self.config.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi DeepSeek: {str(e)}"
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        try:
            # Ensure system prompt is first
            chat_messages = [
                {"role": "system", "content": self.config.system_prompt}
            ]
            
            for msg in messages:
                if msg["role"] != "system":
                    chat_messages.append(msg)
            
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=chat_messages
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi DeepSeek: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# OPENAI
# ══════════════════════════════════════════════════════════════════════════════

class OpenAIProvider(BaseAIProvider):
    """
    OpenAI GPT
    
    API Key: https://platform.openai.com/
    Pricing: Varies by model
    """
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.config.api_key)
            print(f"✓ OpenAI initialized: {self.config.get_model()}")
            
        except ImportError:
            raise ImportError("Chạy: pip install openai")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt or self.config.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi OpenAI: {str(e)}"
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        try:
            chat_messages = [
                {"role": "system", "content": self.config.system_prompt}
            ]
            
            for msg in messages:
                if msg["role"] != "system":
                    chat_messages.append(msg)
            
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=chat_messages
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi OpenAI: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# GROQ (Nhanh nhất)
# ══════════════════════════════════════════════════════════════════════════════

class GroqProvider(BaseAIProvider):
    """
    Groq - Inference siêu nhanh
    
    API Key: https://console.groq.com/
    Pricing: Free tier generous, paid rẻ
    
    Ưu điểm: Tốc độ inference cực nhanh
    """
    
    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._init_client()
    
    def _init_client(self):
        try:
            from groq import Groq
            self.client = Groq(api_key=self.config.api_key)
            print(f"✓ Groq initialized: {self.config.get_model()}")
            
        except ImportError:
            raise ImportError("Chạy: pip install groq")
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt or self.config.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi Groq: {str(e)}"
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        try:
            chat_messages = [
                {"role": "system", "content": self.config.system_prompt}
            ]
            
            for msg in messages:
                if msg["role"] != "system":
                    chat_messages.append(msg)
            
            response = self.client.chat.completions.create(
                model=self.config.get_model(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=chat_messages
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Lỗi Groq: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# AI PROVIDER FACTORY
# ══════════════════════════════════════════════════════════════════════════════

class AIProvider:
    """
    Factory class để tạo AI Provider phù hợp
    
    Usage:
        config = AIConfig(provider="deepseek", api_key="sk-xxx")
        ai = AIProvider(config)
        response = ai.chat("Phân tích VNIndex...")
    """
    
    PROVIDERS = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "deepseek": DeepSeekProvider,
        "openai": OpenAIProvider,
        "groq": GroqProvider,
    }
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._provider = self._create_provider()
    
    def _create_provider(self) -> BaseAIProvider:
        provider_class = self.PROVIDERS.get(self.config.provider.lower())
        
        if not provider_class:
            supported = ", ".join(self.PROVIDERS.keys())
            raise ValueError(f"Provider '{self.config.provider}' không được hỗ trợ. "
                           f"Các provider hỗ trợ: {supported}")
        
        return provider_class(self.config)
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """Gửi prompt và nhận response"""
        return self._provider.chat(prompt, system_prompt)
    
    def chat_with_history(self, messages: List[Dict]) -> str:
        """Chat với lịch sử hội thoại"""
        return self._provider.chat_with_history(messages)
    
    @staticmethod
    def list_providers() -> List[str]:
        """Liệt kê các provider được hỗ trợ"""
        return list(AIProvider.PROVIDERS.keys())


# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON TABLE
# ══════════════════════════════════════════════════════════════════════════════

PROVIDER_COMPARISON = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        SO SÁNH CÁC AI PROVIDERS                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Provider   │ Giá            │ Tốc độ   │ Chất lượng │ Tiếng Việt │ Ghi chú   ║
╠════════════╪════════════════╪══════════╪════════════╪════════════╪═══════════╣
║ DeepSeek   │ ⭐ Rẻ nhất     │ Nhanh    │ Tốt        │ Tốt        │ Khuyến    ║
║            │ $0.14/1M       │          │            │            │ nghị      ║
╠════════════╪════════════════╪══════════╪════════════╪════════════╪═══════════╣
║ Gemini     │ Free tier      │ Nhanh    │ Tốt        │ Khá        │ Free      ║
║            │ rộng rãi       │          │            │            │ nhiều     ║
╠════════════╪════════════════╪══════════╪════════════╪════════════╪═══════════╣
║ Groq       │ Free + Rẻ      │ ⭐ Siêu  │ Khá        │ Khá        │ Nhanh     ║
║            │                │ nhanh    │            │            │ nhất      ║
╠════════════╪════════════════╪══════════╪════════════╪════════════╪═══════════╣
║ Claude     │ Trung bình     │ Trung    │ ⭐ Xuất    │ Rất tốt    │ Phân      ║
║            │ $3/1M in       │ bình     │ sắc        │            │ tích tốt  ║
╠════════════╪════════════════╪══════════╪════════════╪════════════╪═══════════╣
║ OpenAI     │ Cao            │ Trung    │ Tốt        │ Tốt        │ Phổ       ║
║            │ $2.5/1M in     │ bình     │            │            │ biến      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

💡 KHUYẾN NGHỊ:
   • Dùng hàng ngày: DeepSeek (rẻ, chất lượng tốt)
   • Cần nhanh: Groq
   • Phân tích phức tạp: Claude
   • Free: Gemini
"""


def print_comparison():
    """In bảng so sánh"""
    print(PROVIDER_COMPARISON)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

def test_provider(provider: str, api_key: str):
    """Test một provider"""
    print(f"\n{'='*50}")
    print(f"Testing {provider.upper()}...")
    print('='*50)
    
    try:
        config = AIConfig(
            provider=provider,
            api_key=api_key,
            max_tokens=500
        )
        
        ai = AIProvider(config)
        
        response = ai.chat("VNIndex hôm nay 1285 điểm, tăng 5 điểm. Nhận định ngắn gọn xu hướng?")
        
        print(f"\n📝 Response:\n{response[:500]}...")
        print(f"\n✓ {provider} hoạt động OK!")
        
    except Exception as e:
        print(f"✗ Lỗi: {e}")


if __name__ == "__main__":
    print_comparison()
    
    # Uncomment để test
    # test_provider("deepseek", "sk-xxx")
    # test_provider("gemini", "xxx")
