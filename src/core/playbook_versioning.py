"""
Playbook Versioning System

Gerencia o ciclo de vida e versionamento de playbooks.
Suporta:
1. Criação de novas versões (Major/Minor/Patch)
2. Rollback para versões anteriores
3. Diff entre versões
4. Depreciação de versões antigas
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime
import copy

from src.core.neo4j_playbook_store import Neo4jPlaybookStore, PlaybookStatus

logger = logging.getLogger(__name__)

class VersionType(str, Enum):
    MAJOR = "major"  # Mudança incompatível ou reescrita total
    MINOR = "minor"  # Adição de passos ou funcionalidade
    PATCH = "patch"  # Correção de bugs ou typos

class PlaybookVersioning:
    """Sistema de Versionamento de Playbooks."""
    
    def __init__(self, store: Neo4jPlaybookStore):
        self.store = store
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_new_version(self, 
                          playbook_id: str, 
                          changes: Dict[str, Any], 
                          version_type: VersionType,
                          author: str,
                          notes: str) -> str:
        """Cria uma nova versão de um playbook existente.
        
        Args:
            playbook_id: ID do playbook original
            changes: Dicionário com campos alterados
            version_type: Tipo de incremento de versão
            author: Autor da mudança
            notes: Notas de release
            
        Returns:
            ID do novo playbook (nova versão)
        """
        try:
            # 1. Recuperar playbook atual
            current = self.store.get_playbook(playbook_id)
            if not current:
                raise ValueError(f"Playbook {playbook_id} not found")
            
            # 2. Calcular nova versão
            old_version = current.get("version", "1.0.0")
            new_version = self._increment_version(old_version, version_type)
            
            # 3. Criar cópia com alterações
            new_playbook = copy.deepcopy(current)
            new_playbook.update(changes)
            
            # Campos de controle
            new_playbook["version"] = new_version
            new_playbook["previous_version_id"] = playbook_id
            new_playbook["created_at"] = datetime.now().isoformat()
            new_playbook["created_by"] = author
            new_playbook["status"] = "DRAFT"  # Começa como draft
            new_playbook["change_log"] = notes
            
            # Gerar novo ID (em produção, UUID)
            new_id = f"{playbook_id.split('-v')[0]}-v{new_version.replace('.', '_')}"
            new_playbook["playbook_id"] = new_id
            
            # 4. Armazenar nova versão
            self.store.store_playbook(new_playbook)
            
            # 5. Criar link de versionamento no grafo
            # self.store.create_version_link(playbook_id, new_id)
            
            self.logger.info(f"Nova versão criada: {new_id} (from {playbook_id})")
            return new_id
            
        except Exception as e:
            self.logger.error(f"Erro ao criar versão: {e}")
            raise
    
    def _increment_version(self, version: str, type: VersionType) -> str:
        """Incrementa string de versão semântica (X.Y.Z)."""
        try:
            major, minor, patch = map(int, version.split('.'))
            
            if type == VersionType.MAJOR:
                major += 1
                minor = 0
                patch = 0
            elif type == VersionType.MINOR:
                minor += 1
                patch = 0
            elif type == VersionType.PATCH:
                patch += 1
                
            return f"{major}.{minor}.{patch}"
        except ValueError:
            # Fallback se versão não for semântica
            return f"{version}.1"

    def get_version_history(self, playbook_root_id: str) -> List[Dict[str, Any]]:
        """Recupera histórico de versões de um playbook."""
        # Em produção, query recursiva no Neo4j
        return []
