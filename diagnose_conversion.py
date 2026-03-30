#!/usr/bin/env python3
"""
Script de diagnóstico para investigar problemas de conversão TTT.
Execute este script apontando para o diretório de entrada que você está tentando converter.
"""

import os
import sys
import argparse

# Adicionar o diretório atual ao path para importar ttt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ttt.scanner import scan_directory
from ttt.converters.xml_to_revscript import XmlToRevScriptConverter
from ttt.mappings.tfs03_functions import TFS03_TO_1X
from ttt.converters.lua_transformer import LuaTransformer


def diagnose_directory(input_dir: str):
    """Diagnostica a estrutura do diretório e a conversão."""
    
    print("=" * 70)
    print(f"DIAGNÓSTICO DE CONVERSÃO TTT")
    print(f"Diretório: {input_dir}")
    print("=" * 70)
    
    if not os.path.isdir(input_dir):
        print(f"ERRO: Diretório não existe: {input_dir}")
        return
    
    # 1. Escanear o diretório
    print("\n[1/5] ESCANEANDO DIRETÓRIO...")
    scan = scan_directory(input_dir)
    print(scan.summary())
    
    # 2. Verificar arquivos Lua encontrados
    print("\n[2/5] ARQUIVOS LUA ENCONTRADOS:")
    lua_by_dir = {}
    for lua_file in sorted(scan.lua_files):
        rel_path = os.path.relpath(lua_file, input_dir)
        dir_name = os.path.dirname(rel_path)
        if dir_name not in lua_by_dir:
            lua_by_dir[dir_name] = []
        lua_by_dir[dir_name].append(os.path.basename(lua_file))
    
    for dir_name, files in sorted(lua_by_dir.items()):
        print(f"\n  {dir_name or '(root)'}: {len(files)} arquivo(s)")
        for f in files[:10]:  # Mostrar até 10
            print(f"    - {f}")
        if len(files) > 10:
            print(f"    ... e mais {len(files) - 10} arquivo(s)")
    
    # 3. Verificar XMLs e suas entradas
    print("\n[3/5] VERIFICANDO XMLs:")
    
    xml_checks = [
        ("actions", scan.actions_xml, scan.actions_dir),
        ("movements", scan.movements_xml, scan.movements_dir),
        ("talkactions", scan.talkactions_xml, scan.talkactions_dir),
        ("creaturescripts", scan.creaturescripts_xml, scan.creaturescripts_dir),
        ("globalevents", scan.globalevents_xml, scan.globalevents_dir),
    ]
    
    for name, xml_path, scripts_dir in xml_checks:
        print(f"\n  {name.upper()}:")
        if xml_path:
            print(f"    XML: {os.path.relpath(xml_path, input_dir)}")
            if os.path.exists(xml_path):
                with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Contar entradas
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(content)
                    entries = list(root.iter())
                    entry_count = len([e for e in entries if e.tag != root.tag])
                    print(f"    Entradas no XML: {entry_count}")
                except ET.ParseError as e:
                    print(f"    ERRO ao parsear XML: {e}")
            else:
                print(f"    ERRO: XML não existe no caminho especificado!")
        else:
            print(f"    XML: Não encontrado")
        
        if scripts_dir:
            print(f"    Scripts dir: {os.path.relpath(scripts_dir, input_dir)}")
            if os.path.exists(scripts_dir):
                lua_count = sum(1 for _, _, files in os.walk(scripts_dir) 
                              for f in files if f.endswith('.lua'))
                print(f"    Arquivos .lua no diretório: {lua_count}")
            else:
                print(f"    ERRO: Diretório de scripts não existe!")
        else:
            print(f"    Scripts dir: Não encontrado")
    
    # 4. Testar conversão (dry-run)
    print("\n[4/5] TESTANDO CONVERSÃO XML → REVSCRIPT:")
    
    transformer = LuaTransformer(TFS03_TO_1X, "tfs03")
    converter = XmlToRevScriptConverter(lua_transformer=transformer, dry_run=True)
    
    for name, xml_path, scripts_dir in xml_checks:
        if not xml_path or not scripts_dir:
            continue
        
        print(f"\n  Testando {name}...")
        try:
            output_files = converter.convert_xml_file(xml_path, scripts_dir, "")
            reports = converter.pop_file_reports()
            
            success_count = sum(1 for r in reports if r.success)
            error_count = sum(1 for r in reports if not r.success)
            
            print(f"    Arquivos processados: {len(reports)}")
            print(f"    Sucessos: {success_count}")
            print(f"    Erros: {error_count}")
            
            if error_count > 0:
                print(f"    Detalhes dos erros:")
                for r in reports:
                    if not r.success:
                        print(f"      - {os.path.basename(r.source_path)}: {r.error}")
            
            # Verificar se há scripts no diretório que não foram processados
            all_lua_in_dir = set()
            for root, _, files in os.walk(scripts_dir):
                for f in files:
                    if f.endswith('.lua'):
                        full_path = os.path.join(root, f)
                        all_lua_in_dir.add(os.path.normpath(full_path))
            
            processed = set(os.path.normpath(r.source_path) for r in reports if r.source_path)
            not_processed = all_lua_in_dir - processed
            
            if not_processed:
                print(f"    ALERTA: {len(not_processed)} script(s) no diretório não foram processados:")
                for p in list(not_processed)[:5]:
                    print(f"      - {os.path.basename(p)}")
                if len(not_processed) > 5:
                    print(f"      ... e mais {len(not_processed) - 5}")
                    
        except Exception as e:
            print(f"    ERRO durante conversão: {e}")
            import traceback
            traceback.print_exc()
    
    # 5. Verificar problemas comuns
    print("\n[5/5] VERIFICANDO PROBLEMAS COMUNS:")
    
    issues = []
    
    # Verificar se actions.xml existe mas scripts_dir está vazio ou incorreto
    if scan.actions_xml and scan.actions_dir:
        xml_dir = os.path.dirname(scan.actions_xml)
        expected_scripts = os.path.join(xml_dir, 'scripts')
        if os.path.exists(expected_scripts) and scan.actions_dir != expected_scripts:
            issues.append(f"actions_dir aponta para {scan.actions_dir}, mas {expected_scripts} também existe")
    
    # Verificar scripts com caminhos relativos no XML
    for name, xml_path, scripts_dir in xml_checks:
        if not xml_path:
            continue
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            for elem in root.iter():
                script_attr = elem.get('script', '')
                if script_attr and ('/' in script_attr or '\\' in script_attr):
                    issues.append(f"{name}: script '{script_attr}' tem caminho relativo (pode causar problemas)")
        except:
            pass
    
    if issues:
        print("\n  Problemas encontrados:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  Nenhum problema óbvio encontrado.")
    
    print("\n" + "=" * 70)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Diagnostica problemas de conversão TTT')
    parser.add_argument('input_dir', help='Diretório de entrada a ser diagnosticado')
    args = parser.parse_args()
    
    diagnose_directory(args.input_dir)


if __name__ == "__main__":
    main()
