# -*- coding: utf-8 -*-
"""
TSADS - Truth Social Monitor & LLM Semantic Analyzer
This script fetches Donald Trump's posts and analyzes them for market impact
using either NVIDIA NIM (Meta Llama 3.1 8B) or Gemini API (v2.5 Flash), or rule fallback.
"""

import os
import re
import html
from datetime import datetime
import urllib.request
import json

# Dynamic Import for Gemini API (Fallback)
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Backup Rule-Based Keywords Map
KEYWORD_SECTOR_MAP = {
    # Sector: (Keywords, Primary Impact Direction)
    "Automotive": (["auto", "car", "vehicle", "toyota", "ford", "gm", "ev", "tesla"], "NEGATIVE"),
    "Semiconductors": (["chip", "semiconductor", "tsmc", "nvidia", "intel", "taiwan"], "NEGATIVE"),
    "Steel & Metals": (["steel", "aluminum", "metal", "tariff", "tariffs", "trade war", "sanctions"], "NEGATIVE"),
    "Energy & Oil": (["oil", "gas", "drill", "pipeline", "fracking", "energy", "petroleum"], "POSITIVE"),
    "Cryptocurrency": (["bitcoin", "btc", "crypto", "ethereum", "eth", "coin", "solana"], "POSITIVE"),
    "Defense": (["military", "defense", "weapon", "defense spending", "nato", "war", "warfare", "conflict", "combat", "army", "navy", "air force", "pentagon"], "POSITIVE"),
    "Financials": (["bank", "financial", "fed", "deregulation", "invest", "equity", "stake", "merger", "acquisition"], "POSITIVE"),
    "Bonds & Rates": (["rate", "rates", "interest rate", "inflation", "cpi", "ppi", "yield", "rate cut", "rate hike", "fed rate"], "NEGATIVE"),
    "China-Exposure": (["china", "chinese", "beijing", "xi", "tariff", "tariffs", "trade war", "sanctions"], "NEGATIVE"),
}

class TruthSocialMonitor:
    def __init__(self, use_llm=True):
        self.use_llm = use_llm
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        
        self.engine_mode = "RULES"
        
        if self.use_llm:
            if self.nvidia_api_key:
                self.engine_mode = "NVIDIA_NIM"
                self.nim_base_url = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
                self.nim_model = os.environ.get("NVIDIA_NIM_MODEL", "meta/llama-3.1-8b-instruct")
                print(f"[TSADS] NVIDIA NIM mode active (Model: {self.nim_model}).")
            elif self.gemini_api_key and HAS_GEMINI:
                try:
                    self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                    self.engine_mode = "GEMINI"
                    print("[TSADS] Gemini API mode active.")
                except Exception as e:
                    print(f"[TSADS] Warning: Failed to initialize Gemini API: {e}. Falling back to Rules.")
                    self.engine_mode = "RULES"
            else:
                print("[TSADS] No LLM API Keys found in env. Running in Rule-based Mode.")
                self.engine_mode = "RULES"

    def fetch_latest_posts(self, username="realdonaldtrump", mock=False):
        """
        Fetches latest posts from Truth Social.
        If mock=True, returns mock data for testing.
        """
        if mock:
            return self._get_mock_posts()
            
        lookup_url = f"https://truthsocial.com/api/v1/accounts/lookup?acct={username}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        try:
            # 1. Get user ID
            req = urllib.request.Request(lookup_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                user_data = json.loads(response.read().decode("utf-8"))
                user_id = user_data.get("id")
                
            if not user_id:
                print(f"[TSADS] Could not find user id for {username}.")
                return []
                
            # 2. Get posts
            statuses_url = f"https://truthsocial.com/api/v1/accounts/{user_id}/statuses"
            req2 = urllib.request.Request(statuses_url, headers=headers)
            with urllib.request.urlopen(req2, timeout=10) as response2:
                statuses_data = json.loads(response2.read().decode("utf-8"))
                
            posts = []
            for item in statuses_data:
                content_html = item.get("content", "")
                # Clean HTML tags from content
                clean_text = re.sub('<[^<]+?>', '', content_html)
                clean_text = html.unescape(clean_text)
                
                posts.append({
                    "id": item.get("id", str(hash(clean_text))),
                    "text": clean_text,
                    "timestamp": item.get("created_at", ""),
                    "link": item.get("url", "")
                })
                
            print(f"[TSADS] Successfully fetched {len(posts)} live posts.")
            return posts
        except Exception as e:
            print(f"[TSADS] Failed to fetch live posts via API ({e}). Returning empty list to avoid mock data loop.")
            return []

    def analyze_post(self, post_text):
        """
        Analyzes the post text for market sentiment, sectors, and impact direction.
        """
        if self.engine_mode == "NVIDIA_NIM":
            return self._analyze_with_nvidia_nim(post_text)
        elif self.engine_mode == "GEMINI":
            return self._analyze_with_gemini(post_text)
        else:
            return self._analyze_with_rules(post_text)

    def _analyze_with_nvidia_nim(self, post_text):
        """
        Calls NVIDIA NIM API to perform semantic extraction and sentiment scoring.
        """
        prompt = f"""
        You are an elite financial market quant analyzer. Analyze the following social media post from Donald Trump.
        Determine:
        1. Whether the text contains potential stock market or sector-specific impacts (Yes/No).
           CRITICAL RULE: Set has_impact to 'Yes' ONLY if the post contains specific, concrete policy declarations, direct threats (e.g. tariffs, trade wars, sanctions), trade negotiations, direct comments on interest rates, inflation, Federal Reserve policy, geopolitical conflicts/wars, or direct investments/stakes/mergers in companies/sectors.
           If the post is general bragging (e.g. 'BEST ECONOMY EVER'), generic political backing/endorsements of congressmen/candidates, daily greetings, or personal attacks, classify has_impact as 'No' and confidence as low.
        2. The primary sectors affected (e.g., Automotive, Semiconductors, Steel & Metals, Energy & Oil, Cryptocurrency, Defense, Financials, China-Exposure, Bonds & Rates, Safe-Haven & Gold).
        3. The sentiment/impact direction for the affected sectors (POSITIVE / NEGATIVE / NEUTRAL).
        4. The implied trading vehicle direction (CALL / PUT / NONE).
        5. A confidence score between 0.0 and 1.0.

        Output ONLY a valid JSON string with these keys: "has_impact", "sectors", "sentiment", "trading_direction", "confidence", "reason".
        Do not add markdown formatting or code blocks outside the raw JSON.
        
        Post text:
        "{post_text}"
        """
        
        url = f"{self.nim_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.nvidia_api_key}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "model": self.nim_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }).encode("utf-8")
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                result_content = res_data["choices"][0]["message"]["content"]
                
                parsed = json.loads(result_content.strip())
                parsed["timestamp"] = datetime.now().isoformat()
                parsed["text"] = post_text
                return parsed
        except Exception as e:
            print(f"[TSADS NIM] Error during NIM inference: {e}. Falling back to rules.")
            return self._analyze_with_rules(post_text)

    def _analyze_with_gemini(self, post_text):
        """
        Calls Gemini API to perform semantic extraction and sentiment scoring.
        """
        prompt = f"""
        You are an elite financial market quant analyzer. Analyze the following social media post from Donald Trump.
        Determine:
        1. Whether the text contains potential stock market or sector-specific impacts (Yes/No).
           CRITICAL RULE: Set has_impact to 'Yes' ONLY if the post contains specific, concrete policy declarations, direct threats (e.g. tariffs, trade wars, sanctions), trade negotiations, direct comments on interest rates, inflation, Federal Reserve policy, geopolitical conflicts/wars, or direct investments/stakes/mergers in companies/sectors.
           If the post is general bragging (e.g. 'BEST ECONOMY EVER'), generic political backing/endorsements of congressmen/candidates, daily greetings, or personal attacks, classify has_impact as 'No' and confidence as low.
        2. The primary sectors affected (e.g., Automotive, Semiconductors, Steel & Metals, Energy & Oil, Cryptocurrency, Defense, Financials, China-Exposure, Bonds & Rates, Safe-Haven & Gold).
        3. The sentiment/impact direction for the affected sectors (POSITIVE / NEGATIVE / NEUTRAL).
        4. The implied trading vehicle direction (CALL / PUT / NONE).
        5. A confidence score between 0.0 and 1.0.

        Output ONLY a valid JSON string with these keys: "has_impact", "sectors", "sentiment", "trading_direction", "confidence", "reason".
        Do not add markdown formatting or code blocks outside the raw JSON.
        
        Post text:
        "{post_text}"
        """
        try:
            response = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            result_text = response.text.strip()
            
            # Clean possible markdown JSON wrappers
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "", 1)
            if result_text.endswith("```"):
                result_text = result_text[:-3].strip()
            result_text = result_text.strip()
            
            parsed = json.loads(result_text)
            parsed["timestamp"] = datetime.now().isoformat()
            parsed["text"] = post_text
            return parsed
        except Exception as e:
            print(f"[TSADS] Gemini generation error: {e}. Falling back to rules.")
            return self._analyze_with_rules(post_text)

    def _analyze_with_rules(self, post_text):
        """
        Backup rule-based keyword match semantic analyzer.
        """
        text_lower = post_text.lower()
        matched_sectors = []
        sentiment = "NEUTRAL"
        trading_direction = "NONE"
        confidence = 0.5
        reason = "Rule-based backup analysis."
        
        # Simple keyword matching
        for sector, (keywords, default_direction) in KEYWORD_SECTOR_MAP.items():
            for kw in keywords:
                if kw in text_lower:
                    matched_sectors.append(sector)
                    sentiment = default_direction
                    confidence = 0.75
                    break
        
        # Determine trading direction based on sentiment
        if sentiment == "POSITIVE":
            trading_direction = "CALL"
        elif sentiment == "NEGATIVE":
            trading_direction = "PUT"
            
        # Refine if tariff is mentioned
        if "tariff" in text_lower or "tariffs" in text_lower:
            confidence = 0.85
            reason = "Detected tariff/trade policy keyword."
            
        has_impact = len(matched_sectors) > 0
        
        return {
            "text": post_text,
            "timestamp": datetime.now().isoformat(),
            "has_impact": has_impact,
            "sectors": list(set(matched_sectors)) if has_impact else ["General Market"],
            "sentiment": sentiment,
            "trading_direction": trading_direction,
            "confidence": confidence,
            "reason": reason
        }

    def _get_mock_posts(self):
        return [
            {
                "id": "mock_001",
                "text": "Under my administration, we will impose a massive 25% tariff on all imported automobiles and auto parts from Mexico and Europe to protect American workers!",
                "timestamp": datetime.now().isoformat(),
                "link": "https://truthsocial.com/realdonaldtrump/posts/mock_001"
            },
            {
                "id": "mock_002",
                "text": "Bitcoin and Cryptocurrencies are the future! We will establish a National Bitcoin Reserve and make America the crypto capital of the planet. Drill baby drill!",
                "timestamp": datetime.now().isoformat(),
                "link": "https://truthsocial.com/realdonaldtrump/posts/mock_002"
            },
            {
                "id": "mock_003",
                "text": "Had a great meeting with military generals. We are going to rebuild our military and invest heavily in our defense systems. America First!",
                "timestamp": datetime.now().isoformat(),
                "link": "https://truthsocial.com/realdonaldtrump/posts/mock_003"
            }
        ]

if __name__ == "__main__":
    # Self-test demonstration
    monitor = TruthSocialMonitor(use_llm=True)
    posts = monitor.fetch_latest_posts(mock=True)
    print("\n--- Testing Semantic Analysis ---")
    for post in posts[:2]:
        print(f"\nAnalyzing: {post['text']}")
        analysis = monitor.analyze_post(post["text"])
        print("Analysis Result:")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
