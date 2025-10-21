#!/usr/bin/env python3
"""
Fix for unidades-proyecto endpoints filter/limit consistency issue

PROBLEM IDENTIFIED:
- Geometry endpoint: filters first, then applies limit ✅
- Attributes endpoint: applies limit first, then filters ❌

SOLUTION:
- Modify get_unidades_proyecto_attributes to apply limit AFTER client-side filtering
- Ensure both endpoints follow the same filter → limit order
"""

import os
import sys
from pathlib import Path

def fix_attributes_function():
    """Fix the order of limit and filter application in attributes function"""
    
    # Path to the file
    file_path = Path("api/scripts/unidades_proyecto.py")
    
    if not file_path.exists():
        print(f"❌ Error: File {file_path} not found")
        return False
    
    print(f"🔧 Reading {file_path}...")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # The problematic code section that applies limit before filtering
    old_code = """        # Aplicar límite server-side SOLO si se especifica explícitamente
        if limit and limit > 0:
            query = query.limit(limit + (offset or 0))  # Aumentar límite para compensar offset
            server_side_filters_applied.append(f"limit_explícito={limit}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE límite explícito aplicado: {limit}")"""
    
    # The fix: Remove server-side limit application, apply it after client-side filtering
    new_code = """        # ✅ FIX: NO aplicar límite server-side cuando hay filtros client-side
        # El límite se aplicará DESPUÉS de los filtros client-side para consistencia
        # with geometry endpoint behavior
        server_side_limit_skipped = False
        if limit and limit > 0:
            server_side_limit_skipped = True
            print(f"📋 DEBUG: ⏭️ SERVER-SIDE límite pospuesto para aplicar después de filtros: {limit}")"""
    
    if old_code not in content:
        print("❌ Error: Could not find the target code section to fix")
        print("The file may have been already modified or the code structure changed")
        return False
    
    # Replace the problematic section
    content = content.replace(old_code, new_code)
    
    # Also need to fix the final limit application section
    old_limit_section = """        # Aplicar límite después de filtros client-side
        original_count = len(attributes_data)
        if limit and limit > 0:
            attributes_data = attributes_data[:limit]
            print(f"📋 DEBUG: Aplicando límite de {limit} registros")"""
    
    new_limit_section = """        # ✅ FIX: Aplicar límite después de filtros client-side (CONSISTENTE con geometry endpoint)
        original_count = len(attributes_data)
        if limit and limit > 0:
            # Apply offset first (if any), then limit
            if offset and offset > 0:
                attributes_data = attributes_data[offset:]
                print(f"📋 DEBUG: Aplicando offset de {offset} registros")
            
            attributes_data = attributes_data[:limit]
            print(f"📋 DEBUG: ✅ LÍMITE APLICADO DESPUÉS DE FILTROS: {limit} registros (consistente con geometry endpoint)")"""
    
    if old_limit_section in content:
        content = content.replace(old_limit_section, new_limit_section)
    else:
        print("⚠️ Warning: Could not find limit application section, but main fix applied")
    
    # Create backup
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        with open(file_path, 'r', encoding='utf-8') as original:
            f.write(original.read())
    
    print(f"💾 Backup created: {backup_path}")
    
    # Write the fixed content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fix applied successfully!")
    print("\n🔍 Changes made:")
    print("1. Removed server-side limit application when filters are present")
    print("2. Enhanced client-side limit application to be consistent with geometry endpoint")
    print("3. Improved offset handling in the client-side section")
    
    return True

def create_test_script():
    """Create a test script to validate the fix"""
    
    test_content = '''#!/usr/bin/env python3
"""
Test script to validate the filter consistency fix

This script tests both endpoints with the same filter and limit parameters
to ensure they return consistent results.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.scripts.unidades_proyecto import (
    get_unidades_proyecto_geometry,
    get_unidades_proyecto_attributes
)

async def test_consistency():
    """Test that both endpoints return consistent results"""
    
    print("🧪 Testing filter/limit consistency after fix...")
    
    # Test parameters that caused the original issue
    test_cases = [
        {
            "filters": {"comuna_corregimiento": "COMUNA 02"},
            "limit": 10,
            "description": "COMUNA 02 with limit 10"
        },
        {
            "filters": {"comuna_corregimiento": "COMUNA 02"},
            "limit": 25,
            "description": "COMUNA 02 with limit 25"
        },
        {
            "filters": {"comuna_corregimiento": "COMUNA 02"},
            "limit": 50,
            "description": "COMUNA 02 with limit 50"
        },
        {
            "filters": {"comuna_corregimiento": "COMUNA 02"},
            "limit": None,
            "description": "COMUNA 02 without limit"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\\n📋 Test Case {i}: {case['description']}")
        
        # Test geometry endpoint
        geometry_filters = case["filters"].copy()
        if case["limit"]:
            geometry_filters["limit"] = case["limit"]
            
        geometry_result = await get_unidades_proyecto_geometry(geometry_filters)
        
        # Test attributes endpoint  
        attributes_result = await get_unidades_proyecto_attributes(
            filters=case["filters"],
            limit=case["limit"]
        )
        
        # Extract counts
        if geometry_result.get("type") == "FeatureCollection":
            geometry_count = len(geometry_result.get("features", []))
        else:
            geometry_count = geometry_result.get("count", 0)
            
        attributes_count = attributes_result.get("count", 0)
        
        # Check consistency
        if geometry_count == attributes_count:
            print(f"   ✅ CONSISTENT: Geometry {geometry_count}, Attributes {attributes_count}")
        else:
            print(f"   ❌ INCONSISTENT: Geometry {geometry_count}, Attributes {attributes_count}")
            print(f"   📊 Difference: {abs(geometry_count - attributes_count)}")
        
        # Show total before limit for attributes
        total_before = attributes_result.get("total_before_limit", "N/A")
        print(f"   📈 Total before limit (attributes): {total_before}")

if __name__ == "__main__":
    asyncio.run(test_consistency())
'''
    
    test_file = Path("test_filter_consistency_fix.py")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"🧪 Test script created: {test_file}")
    return test_file

def main():
    """Main function to apply the fix"""
    
    print("🔧 Unidades Proyecto Filter Consistency Fix")
    print("=" * 50)
    
    print("\n📋 Problem Summary:")
    print("- Geometry endpoint: filters first ✅, then limit")  
    print("- Attributes endpoint: limit first ❌, then filters")
    print("- This causes inconsistent results when both filter and limit are used")
    
    print("\\n🛠️ Solution:")
    print("- Modify attributes endpoint to apply limit AFTER filtering")
    print("- Make both endpoints follow the same order: filter → limit")
    
    # Apply the fix
    if fix_attributes_function():
        print("\\n✅ Fix applied successfully!")
        
        # Create test script
        test_file = create_test_script()
        
        print("\\n🚀 Next Steps:")
        print("1. Restart your API server to load the changes")
        print(f"2. Run the test script: python {test_file}")
        print("3. Test the endpoints with the original problematic parameters")
        print("4. Both endpoints should now return consistent results")
        
        print("\\n📝 Test Commands:")
        print('curl "https://gestorproyectoapi-production.up.railway.app/unidades-proyecto/geometry?comuna_corregimiento=COMUNA%2002&limit=25"')
        print('curl "https://gestorproyectoapi-production.up.railway.app/unidades-proyecto/attributes?comuna_corregimiento=COMUNA%2002&limit=25"')
        
        return True
    else:
        print("\\n❌ Fix failed. Please check the error messages above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)