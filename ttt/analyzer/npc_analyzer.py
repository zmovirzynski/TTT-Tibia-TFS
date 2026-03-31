"""
NPC Conversation Analyzer — STUB

Status: Stub. Estrutura existe mas todas as análises retornam placeholders vazios.
Não integrado ao CLI (ttt analyze). Não pronto para uso em produção.

Para contribuir: implementar parse_npc_xml() e parse_npc_lua() com parsing real
de scripts de NPC do TFS, e integrar ao AnalyzeEngine.
"""

import os
from typing import List, Dict, Any

class NPCConversationAnalyzer:
    def __init__(self, npc_dir: str, items_xml: str = None):
        self.npc_dir = npc_dir
        self.items_xml = items_xml
        self.npcs = []  # List of parsed NPCs

    def load_npcs(self):
        """Carrega e parseia todos os NPCs do diretório."""
        npc_files = []
        for root, dirs, files in os.walk(self.npc_dir):
            for file in files:
                if file.endswith('.xml') or file.endswith('.lua'):
                    npc_files.append(os.path.join(root, file))
        self.npcs = []
        for npc_file in npc_files:
            if npc_file.endswith('.xml'):
                npc_data = self.parse_npc_xml(npc_file)
            else:
                npc_data = self.parse_npc_lua(npc_file)
            if npc_data:
                self.npcs.append(npc_data)

    def parse_npc_xml(self, path: str) -> Dict[str, Any]:
        """Parseia arquivo XML de NPC e retorna estrutura de conversação."""
        # TODO: Implementar parsing real
        return {'file': path, 'type': 'xml', 'keywords': [], 'shop_items': [], 'greet': False, 'farewell': False, 'responses': [], 'graph': {}}

    def parse_npc_lua(self, path: str) -> Dict[str, Any]:
        """Parseia script Lua de NPC e retorna estrutura de conversação."""
        # TODO: Implementar parsing real
        return {'file': path, 'type': 'lua', 'keywords': [], 'shop_items': [], 'greet': False, 'farewell': False, 'responses': [], 'graph': {}}

    def detect_loops(self) -> Dict[str, Any]:
        """Detecta loops infinitos em conversação."""
        result = {}
        for npc in self.npcs:
            # Placeholder: always returns no loops
            result[npc['file']] = {'has_loop': False, 'details': 'Não implementado'}
        return result

    def detect_duplicate_keywords(self) -> Dict[str, Any]:
        """Detecta keywords duplicadas em cada NPC."""
        result = {}
        for npc in self.npcs:
            keywords = npc.get('keywords', [])
            duplicates = [kw for kw in set(keywords) if keywords.count(kw) > 1]
            result[npc['file']] = {'duplicates': duplicates}
        return result

    def detect_unreachable_responses(self) -> Dict[str, Any]:
        """Detecta respostas inalcançáveis."""
        result = {}
        for npc in self.npcs:
            # Placeholder: always returns all reachable
            result[npc['file']] = {'unreachable': []}
        return result

    def check_greet_farewell(self) -> Dict[str, Any]:
        """Verifica se NPCs possuem greet/farewell."""
        result = {}
        for npc in self.npcs:
            greet = npc.get('greet', False)
            farewell = npc.get('farewell', False)
            result[npc['file']] = {'greet': greet, 'farewell': farewell}
        return result

    def validate_shop_items(self) -> Dict[str, Any]:
        """Valida se itens de shop existem no items.xml."""
        # Placeholder: no validation, just returns all items as valid
        result = {}
        for npc in self.npcs:
            items = npc.get('shop_items', [])
            result[npc['file']] = {'invalid_items': []}
        return result

    def generate_visual_graph(self, output_path: str) -> None:
        """Gera grafo visual (Mermaid/DOT) da conversação."""
        # Stub: gera um grafo Mermaid simples para cada NPC
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('```mermaid\ngraph TD\n')
            for npc in self.npcs:
                npc_name = os.path.basename(npc['file'])
                f.write(f'    {npc_name}((NPC))\n')
                for kw in npc.get('keywords', []):
                    f.write(f'    {npc_name} --> {kw}\n')
            f.write('```\n')

    def analyze(self) -> Dict[str, Any]:
        """Executa todas as análises e retorna relatório consolidado."""
        return {
            'loops': self.detect_loops(),
            'duplicate_keywords': self.detect_duplicate_keywords(),
            'unreachable_responses': self.detect_unreachable_responses(),
            'greet_farewell': self.check_greet_farewell(),
            'shop_items': self.validate_shop_items(),
        }

# CLI stub
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NPC Conversation Analyzer")
    parser.add_argument("npc_dir", help="Diretório com scripts de NPC")
    parser.add_argument("--items-xml", help="Caminho para items.xml", default=None)
    parser.add_argument("--graph", help="Salvar grafo visual em arquivo", default=None)
    args = parser.parse_args()

    analyzer = NPCConversationAnalyzer(args.npc_dir, items_xml=args.items_xml)
    analyzer.load_npcs()
    report = analyzer.analyze()
    print("\nNPC Conversation Analysis Report\n" + "="*60)
    for npc in analyzer.npcs:
        fname = os.path.basename(npc['file'])
        print(f"\nNPC: {fname}")
        loops = report['loops'].get(npc['file'], {})
        dups = report['duplicate_keywords'].get(npc['file'], {})
        unreachable = report['unreachable_responses'].get(npc['file'], {})
        greet = report['greet_farewell'].get(npc['file'], {})
        shop = report['shop_items'].get(npc['file'], {})
        print(f"  ✓ Greet detected" if greet.get('greet') else "  ✗ Greet missing")
        print(f"  ✓ Farewell detected" if greet.get('farewell') else "  ✗ Farewell missing")
        if dups.get('duplicates'):
            for kw in dups['duplicates']:
                print(f"  ✗ Keyword '{kw}' handled multiple times")
        else:
            print("  ✓ All keywords unique")
        if shop.get('invalid_items'):
            for item in shop['invalid_items']:
                print(f"  ✗ Shop item '{item}' not found in items.xml")
        else:
            print("  ✓ All shop items valid")
        print(f"  ✓ No infinite loops detected" if not loops.get('has_loop') else "  ✗ Infinite loop detected")
        if unreachable.get('unreachable'):
            for resp in unreachable['unreachable']:
                print(f"  ✗ Response '{resp}' unreachable")
        else:
            print("  ✓ All responses reachable")
    if args.graph:
        analyzer.generate_visual_graph(args.graph)
        print(f"\nVisual graph saved to {args.graph}")
