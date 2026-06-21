"""
Consistent Hashing Ring
-----------------------
Maps arbitrary string keys to one of N physical nodes using a virtual-node
ring. Each physical node is represented by V virtual nodes (replicas) spread
around a 2^32 hash ring. A key is hashed, then we walk clockwise on the ring
to find the first virtual node whose position is >= the key's hash — that
virtual node's owner becomes the target physical node.

Using virtual nodes provides much better load distribution than mapping one
physical node per ring position, especially with small node counts.
"""

import hashlib
import bisect
from typing import List, Optional


VIRTUAL_NODES = 150  # replicas per physical node


class ConsistentHashRing:
    def __init__(self, nodes: List[str], virtual_nodes: int = VIRTUAL_NODES):
        self._virtual_nodes = virtual_nodes
        # ring maps hash position -> node label
        self._ring: dict[int, str] = {}
        # sorted list of all hash positions for O(log n) lookup
        self._sorted_keys: List[int] = []

        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        """MD5 gives a 128-bit int; fold it into 32 bits for a manageable ring."""
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest, 16) & 0xFFFFFFFF

    def add_node(self, node: str) -> None:
        for i in range(self._virtual_nodes):
            vnode_key = f"{node}#vn{i}"
            pos = self._hash(vnode_key)
            self._ring[pos] = node
            bisect.insort(self._sorted_keys, pos)

    def remove_node(self, node: str) -> None:
        for i in range(self._virtual_nodes):
            vnode_key = f"{node}#vn{i}"
            pos = self._hash(vnode_key)
            if pos in self._ring and self._ring[pos] == node:
                del self._ring[pos]
                idx = bisect.bisect_left(self._sorted_keys, pos)
                if idx < len(self._sorted_keys) and self._sorted_keys[idx] == pos:
                    self._sorted_keys.pop(idx)

    def get_node(self, key: str) -> Optional[str]:
        """Return the node responsible for the given key."""
        if not self._ring:
            return None
        h = self._hash(key)
        # Find first vnode position >= h (clockwise walk)
        idx = bisect.bisect_left(self._sorted_keys, h)
        # Wrap around to the first position if we've passed the end
        if idx == len(self._sorted_keys):
            idx = 0
        return self._ring[self._sorted_keys[idx]]

    def get_node_index(self, key: str, nodes: List[str]) -> int:
        """Return the 0-based index of the responsible node in the original list."""
        node = self.get_node(key)
        if node is None:
            return 0
        try:
            return nodes.index(node)
        except ValueError:
            return 0
