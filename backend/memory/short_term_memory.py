"""
Short-Term Memory (Sliding Window)

Maintains recent conversational context for fluid debate continuity.
Implements a circular buffer with configurable window size.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Deque
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class Message:
    """A single message in the conversation"""
    role: str  # "user", "assistant", "moderator", "proponent", "opponent", etc.
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        """Create from dictionary"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def format_for_context(self) -> str:
        """Format message for inclusion in context payload"""
        return f"{self.role.upper()}: {self.content}"


class ShortTermMemory:
    """
    Manages short-term conversational memory using a sliding window.
    
    This is ZONE 3 in the Hybrid Memory System:
    - Stores last k messages in chronological order
    - Oldest messages are automatically evicted when window is full
    - Provides formatted context for LLM prompts
    """
    
    def __init__(self, window_size: int = 4):
        """
        Initialize short-term memory.
        
        Args:
            window_size: Maximum number of recent messages to retain
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.window_size = window_size
        self.messages: Deque[Message] = deque(maxlen=window_size)
        
        self.logger.info(f"Short-term memory initialized with window size: {window_size}")
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a new message to short-term memory.
        Automatically evicts oldest message if window is full.
        
        Args:
            role: Speaker role (user, assistant, agent, etc.)
            content: Message content
            metadata: Optional metadata (debate_id, turn_number, etc.)
            
        Returns:
            The created Message object
        """
        if not content or not content.strip():
            self.logger.warning("Attempted to add empty message")
            return None
        
        message = Message(
            role=role,
            content=content.strip(),
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        # Add to deque (automatically evicts oldest if full)
        self.messages.append(message)
        
        self.logger.debug(f"Added message from {role} (queue size: {len(self.messages)}/{self.window_size})")
        return message
    
    def get_messages(self, count: Optional[int] = None) -> List[Message]:
        """
        Get recent messages from short-term memory.
        
        Args:
            count: Number of recent messages to retrieve (None = all)
            
        Returns:
            List of messages in chronological order (oldest first)
        """
        if count is None:
            return list(self.messages)
        
        # Get last 'count' messages
        return list(self.messages)[-count:]
    
    def get_context_string(
        self,
        count: Optional[int] = None,
        format_style: str = "conversational"
    ) -> str:
        """
        Get formatted context string for LLM prompt (ZONE 3).
        
        Args:
            count: Number of recent messages to include
            format_style: "conversational" or "structured"
            
        Returns:
            Formatted context string
        """
        messages = self.get_messages(count)
        
        if not messages:
            return ""
        
        if format_style == "conversational":
            # Natural conversation format
            lines = ["RECENT CONVERSATION:"]
            for msg in messages:
                lines.append(msg.format_for_context())
            return "\n".join(lines)
        
        elif format_style == "structured":
            # Structured format with metadata
            lines = ["--- SHORT-TERM MEMORY (Recent Context) ---"]
            for i, msg in enumerate(messages, 1):
                lines.append(f"[Turn {i}] {msg.role.upper()}:")
                lines.append(f"  {msg.content}")
                if msg.metadata:
                    lines.append(f"  Metadata: {json.dumps(msg.metadata, default=str)}")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unknown format_style: {format_style}")
    
    def clear(self):
        """Clear all messages from short-term memory"""
        self.messages.clear()
        self.logger.info("Short-term memory cleared")
    
    def resize_window(self, new_size: int):
        """
        Change the window size, potentially evicting old messages.
        
        Args:
            new_size: New window size
        """
        if new_size < 1:
            raise ValueError("Window size must be at least 1")
        
        old_size = self.window_size
        self.window_size = new_size
        
        # Create new deque with new size
        new_deque = deque(self.messages, maxlen=new_size)
        self.messages = new_deque
        
        self.logger.info(f"Window size changed: {old_size} -> {new_size} (current: {len(self.messages)} messages)")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of short-term memory"""
        return {
            "window_size": self.window_size,
            "current_count": len(self.messages),
            "capacity_used": f"{len(self.messages)}/{self.window_size}",
            "oldest_timestamp": self.messages[0].timestamp.isoformat() if self.messages else None,
            "newest_timestamp": self.messages[-1].timestamp.isoformat() if self.messages else None,
            "roles": list(set(msg.role for msg in self.messages))
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export memory state for serialization"""
        return {
            "window_size": self.window_size,
            "messages": [msg.to_dict() for msg in self.messages]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShortTermMemory':
        """Create instance from serialized data"""
        memory = cls(window_size=data['window_size'])
        for msg_data in data['messages']:
            msg = Message.from_dict(msg_data)
            memory.messages.append(msg)
        return memory
    
    def __len__(self) -> int:
        """Get current number of messages"""
        return len(self.messages)
    
    def __repr__(self) -> str:
        return f"ShortTermMemory(size={len(self)}/{self.window_size}, roles={len(set(msg.role for msg in self.messages))})"
