import ifcopenshell
import os
import sys
import time
import traceback
import subprocess
import tempfile
from ifcopenshell.util import shape, representation, element
import ifcpatch
from ifcopenshell.api import geometry

def optimize_ifc(input_path, output_path, options=None):
    """Optimize IFC file with selected options."""
    print(f"Loading IFC file: {input_path}")
    start_time = time.time()
    
    try:
        # Schema conversion (if enabled)
        if options and options.get("convert_schema"):
            temp_path = "temp_converted.ifc"
            convert_schema(input_path, temp_path, options["target_schema"])
            input_path = temp_path

        # Load the (possibly converted) model
        model = ifcopenshell.open(input_path)
        
        # Default options if none provided
        if options is None:
            options = {
                'remove_unused_spaces': True,
                'remove_metadata': True,
                'remove_empty_attributes': True,
                'remove_unused_property_sets': True,
                'remove_unused_materials': True,
                'remove_unused_classifications': True,
                'remove_small_elements': 0.001,
                'remove_orphaned_entities': True,
                'deduplicate_geometry': True,
                'flatten_spatial_structure': True,
                'simplify_geometry': 'medium'
            }

        initial_size = os.path.getsize(input_path) / (1024 * 1024)
        print(f"Initial file size: {initial_size:.2f} MB")
        
        # Perform optimizations
        stats = {}
        if options.get('remove_unused_spaces', False):
            stats['spaces'] = remove_unused_spaces(model)
        if options.get('remove_metadata', False):
            stats['metadata'] = remove_metadata(model)
        if options.get('remove_empty_attributes', False):
            stats['empty_attrs'] = remove_empty_attributes(model)
        if options.get('remove_unused_property_sets', False):
            stats['psets'] = remove_unused_property_sets(model)
        if options.get('remove_unused_materials', False):
            stats['materials'] = remove_unused_materials(model)
        if options.get('remove_unused_classifications', False):
            stats['classifications'] = remove_unused_classifications(model)
        if 'remove_small_elements' in options and options['remove_small_elements'] is not None:
            min_vol = float(options['remove_small_elements'])
            stats['small_elements'] = remove_small_elements(model, min_vol)
        if options.get('remove_orphaned_entities', False):
            stats['orphans'] = remove_orphaned_entities(model)
        if options.get('deduplicate_geometry', False):
            stats['duplicate_geo'] = deduplicate_geometry(model)
        if options.get('flatten_spatial_structure', False):
            stats['spatial'] = flatten_spatial_structure(model)
        if options.get('simplify_geometry') and options.get('simplify_geometry') != 'none':
            detail_level = options['simplify_geometry']
            stats['simplified_geo'] = simplify_geometry(model, detail_level)

        # Save optimized IFC
        optimized_ifc_path = output_path
        model.write(optimized_ifc_path)

        # Cleanup temp file if conversion was done
        if options and options.get('convert_schema', False) and os.path.exists("temp_converted.ifc"):
            os.remove("temp_converted.ifc")

        # Validation and results
        print("Validating optimized file...")
        test_model = ifcopenshell.open(optimized_ifc_path)
        print("Validation successful.")

        final_size = os.path.getsize(optimized_ifc_path) / (1024 * 1024)
        print(f"\nOptimization removed:")
        for key, value in stats.items():
            print(f"- {value} {key.replace('_', ' ')}")
        print(f"\nFinal size: {final_size:.2f} MB")
        print(f"Size reduction: {initial_size - final_size:.2f} MB ({(1 - final_size/initial_size)*100:.2f}%)")
        print(f"Time taken: {time.time() - start_time:.2f}s")
        
        # Convert to 3DS if requested
        if options.get('convert_to_3ds', False):
            output_3ds_path = os.path.splitext(output_path)[0] + '.3ds'
            convert_to_3ds(optimized_ifc_path, output_3ds_path)
            stats['converted_to_3ds'] = True

        return stats

    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Optimization failed: {str(e)}")

def convert_to_3ds(ifc_path, output_3ds_path):
    """Convert IFC to OBJ format."""
    try:
        # Convert IFC to OBJ using IfcConvert or ifcopenshell
        output_obj_path = os.path.splitext(output_3ds_path)[0] + '.obj'
        
        # Check if IfcConvert is available
        try:
            # Try to use IfcConvert from ifcopenshell
            ifcconvert_cmd = "IfcConvert"
            subprocess.run([ifcconvert_cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        except (FileNotFoundError, subprocess.SubprocessError):
            # If not found, try to use the Python API
            print("IfcConvert command not found, using ifcopenshell Python API for conversion")
            convert_ifc_to_obj_using_ifcopenshell(ifc_path, output_obj_path)
        else:
            # Use IfcConvert command line tool
            print(f"Converting IFC to OBJ using IfcConvert: {ifc_path} -> {output_obj_path}")
            subprocess.run([ifcconvert_cmd, ifc_path, output_obj_path], check=True)
            
        return True
            
    except Exception as e:
        print(f"Error during conversion to OBJ: {str(e)}")
        traceback.print_exc()
        raise RuntimeError(f"OBJ conversion failed: {str(e)}")

def convert_ifc_to_obj_using_ifcopenshell(ifc_path, obj_path):
    """Convert IFC to OBJ using ifcopenshell Python API."""
    try:
        # Load the IFC file
        model = ifcopenshell.open(ifc_path)
        
        # Create a settings object for the conversion
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        
        # Open the OBJ file for writing
        with open(obj_path, 'w') as obj_file:
            obj_file.write("# OBJ file generated from IFC using ifcopenshell\n")
            
            # Track vertices and faces for the OBJ file
            vertex_index = 1
            vertices = []
            faces = []
            
            # Process each product with geometry
            for product in model.by_type("IfcProduct"):
                if not product.Representation:
                    continue
                
                try:
                    # Create shape from product
                    shape = ifcopenshell.geom.create_shape(settings, product)
                    
                    # Get geometry data
                    verts = shape.geometry.verts
                    faces_data = shape.geometry.faces
                    
                    # Add vertices to the list
                    product_vertices = []
                    for i in range(0, len(verts), 3):
                        vertex = (verts[i], verts[i+1], verts[i+2])
                        vertices.append(f"v {vertex[0]} {vertex[1]} {vertex[2]}")
                        product_vertices.append(vertex_index)
                        vertex_index += 1
                    
                    # Add faces to the list
                    for i in range(0, len(faces_data), 3):
                        face = (faces_data[i], faces_data[i+1], faces_data[i+2])
                        faces.append(f"f {product_vertices[face[0]]} {product_vertices[face[1]]} {product_vertices[face[2]]}")
                
                except Exception as e:
                    print(f"Error processing {product.is_a()}: {str(e)}")
                    continue
            
            # Write vertices and faces to the OBJ file
            for vertex in vertices:
                obj_file.write(vertex + "\n")
            
            for face in faces:
                obj_file.write(face + "\n")
        
        print(f"Successfully converted IFC to OBJ using ifcopenshell: {obj_path}")
        
    except Exception as e:
        print(f"Error in ifcopenshell OBJ conversion: {str(e)}")
        traceback.print_exc()
        raise RuntimeError(f"IFC to OBJ conversion failed: {str(e)}")

def convert_schema(input_path, output_path, target_schema):
    """Convert IFC schema version."""
    try:
        # Use ifcopenshell's schema migration capability
        print(f"Converting schema to {target_schema}...")
        
        # Load the source model
        source_model = ifcopenshell.open(input_path)
        
        # Create a new file with the target schema
        target_model = ifcopenshell.file(schema=target_schema)
        
        # Use ifcpatch for schema migration if available
        try:
            ifcpatch.execute({"input": input_path, "output": output_path, "recipe": "ChangeSchema", "arguments": [target_schema]})
            return
        except (ImportError, AttributeError) as e:
            print(f"ifcpatch schema migration not available: {e}. Using manual migration.")
        
        # Manual migration as fallback
        migrated_entities = {}

        # Migrate owner history first
        for history in source_model.by_type("IfcOwnerHistory"):
            info = history.get_info()
            info.pop("type", None)  # Remove 'type' key if it exists
            migrated_entities[history.id()] = target_model.create_entity(
                "IfcOwnerHistory",
                **info  # Now safe to unpack
            )

        # Migrate other entities
        for source_entity in source_model:
            if source_entity.id() in migrated_entities:
                continue

            try:
                info = source_entity.get_info()
                info.pop("type", None)  # Remove 'type' key
                target_entity = target_model.create_entity(
                    source_entity.is_a(),
                    **info
                )
                migrated_entities[source_entity.id()] = target_entity

            except Exception as e:
                print(f"Skipping {source_entity.is_a()} (#{source_entity.id()}): {str(e)}")

        target_model.write(output_path)
        print(f"Schema conversion completed: {output_path}")
        
    except Exception as e:
        raise RuntimeError(f"Schema conversion failed: {str(e)}")

def simplify_geometry(model, detail_level="medium"):
    """Simplify geometry based on detail level."""
    simplified = 0
    settings = ifcopenshell.geom.settings()
    
    # Get the geometric context
    context = representation.get_context(model, "Model", "Body", "MODEL_VIEW")

    # Fallback: get the first IfcGeometricRepresentationContext if utility fails
    if context is None:
        contexts = model.by_type("IfcGeometricRepresentationContext")
        if contexts:
            context = contexts[0]
        else:
            raise RuntimeError("No IfcGeometricRepresentationContext found in the model.")
    
    # Set simplification level parameters
    if detail_level.lower() == "low":
        angle_tolerance = 30  # degrees
        distance_tolerance = 0.05  # meters
    elif detail_level.lower() == "medium":
        angle_tolerance = 20  # degrees
        distance_tolerance = 0.02  # meters
    elif detail_level.lower() == "high":
        angle_tolerance = 10  # degrees
        distance_tolerance = 0.01  # meters
    else:
        # Default to medium if invalid value
        angle_tolerance = 20
        distance_tolerance = 0.02
    
    # Convert angle to radians
    angle_tolerance_rad = angle_tolerance * 3.14159 / 180.0
    
    # Apply simplification to each product
    for product in model.by_type("IfcProduct"):
        if not product.Representation:
            continue
            
        try: # Outer try block for the whole product processing
            # Get the shape representation
            shape_representation = None
            for rep in product.Representation.Representations:
                if rep.RepresentationIdentifier == "Body":
                    shape_representation = rep
                    break
            
            if not shape_representation:
                continue
                
            # Skip products with certain representation types that shouldn't be simplified
            if shape_representation.RepresentationType in ["MappedRepresentation"]:
                continue
                
            # Create shape from product
            shape = ifcopenshell.geom.create_shape(settings, product)
            
            # Skip if shape creation failed
            if not shape:
                continue
                
            # Get geometry data
            verts = shape.geometry.verts
            faces = shape.geometry.faces
            
            # Skip if no geometry
            if len(verts) == 0 or len(faces) == 0:
                continue
                
            # Simplify based on product type and detail level
            if product.is_a() in ["IfcWall", "IfcSlab", "IfcRoof"]:
                # For planar elements, try to use extrusion where possible
                try: # Inner try for extrusion
                    # Calculate bounding dimensions
                    x_coords = verts[0::3]
                    y_coords = verts[1::3]
                    z_coords = verts[2::3]
                    
                    if len(x_coords) == 0:
                        continue
                        
                    width = max(x_coords) - min(x_coords)
                    depth = max(y_coords) - min(y_coords)
                    height = max(z_coords) - min(z_coords)
                    
                    # Create profile and extrusion
                    profile = model.createIfcRectangleProfileDef(
                        "AREA", None, 
                        model.createIfcAxis2Placement2D(),
                        width, depth
                    )
                    
                    extrusion = model.createIfcExtrudedAreaSolid(
                        profile,
                        model.createIfcAxis2Placement3D(),
                        model.createIfcDirection((0.0, 0.0, 1.0)),
                        height
                    )
                    
                    # Create shape representation
                    body = model.createIfcShapeRepresentation(
                        ContextOfItems=context,
                        RepresentationIdentifier="Body",
                        RepresentationType="SweptSolid",
                        Items=[extrusion]
                    )
                    
                    # Assign the representation to the product
                    ifcopenshell.api.run(
                        "geometry.assign_representation",
                        model,
                        product=product,
                        representation=body
                    )
                    
                    simplified += 1
                except Exception as e:
                    print(f"Error simplifying {product.is_a()} with extrusion: {str(e)}")
                    continue # Continues to the next product in the outer loop
            else:
                # For other elements, use faceted brep with reduced detail
                try:
                    # Calculate bounding dimensions
                    x_coords = verts[0::3]
                    y_coords = verts[1::3]
                    z_coords = verts[2::3]
                    
                    if len(x_coords) == 0:
                        continue
                    
                    # Create a new shape representation
                    items = []
                    
                    # Create a simplified brep
                    outer_curve_loop = model.createIfcPolyLoop([
                        model.createIfcCartesianPoint((min(x_coords), min(y_coords), min(z_coords))),
                        model.createIfcCartesianPoint((max(x_coords), min(y_coords), min(z_coords))),
                        model.createIfcCartesianPoint((max(x_coords), max(y_coords), min(z_coords))),
                        model.createIfcCartesianPoint((min(x_coords), max(y_coords), min(z_coords)))
                    ])
                    
                    face = model.createIfcFace([model.createIfcFaceOuterBound(outer_curve_loop, True)])
                    
                    # Create a closed shell with 6 faces (box)
                    faces_list = [face]
                    
                    # Add top face
                    top_curve_loop = model.createIfcPolyLoop([
                        model.createIfcCartesianPoint((min(x_coords), min(y_coords), max(z_coords))),
                        model.createIfcCartesianPoint((max(x_coords), min(y_coords), max(z_coords))),
                        model.createIfcCartesianPoint((max(x_coords), max(y_coords), max(z_coords))),
                        model.createIfcCartesianPoint((min(x_coords), max(y_coords), max(z_coords)))
                    ])
                    faces_list.append(model.createIfcFace([model.createIfcFaceOuterBound(top_curve_loop, True)]))
                    
                    # Add side faces
                    for i in range(4):
                        j = (i + 1) % 4
                        side_curve_loop = model.createIfcPolyLoop([
                            model.createIfcCartesianPoint((min(x_coords) if i == 0 or i == 3 else max(x_coords), 
                                                          min(y_coords) if i == 0 or i == 1 else max(y_coords), 
                                                          min(z_coords))),
                            model.createIfcCartesianPoint((min(x_coords) if j == 0 or j == 3 else max(x_coords), 
                                                          min(y_coords) if j == 0 or j == 1 else max(y_coords), 
                                                          min(z_coords))),
                            model.createIfcCartesianPoint((min(x_coords) if j == 0 or j == 3 else max(x_coords), 
                                                          min(y_coords) if j == 0 or j == 1 else max(y_coords), 
                                                          max(z_coords))),
                            model.createIfcCartesianPoint((min(x_coords) if i == 0 or i == 3 else max(x_coords), 
                                                          min(y_coords) if i == 0 or i == 1 else max(y_coords), 
                                                          max(z_coords)))
                        ])
                        faces_list.append(model.createIfcFace([model.createIfcFaceOuterBound(side_curve_loop, True)]))
                    
                    shell = model.createIfcClosedShell(faces_list)
                    brep = model.createIfcFacetedBrep(shell)
                    items.append(brep)
                    
                    # Create shape representation
                    body = model.createIfcShapeRepresentation(
                        ContextOfItems=context,
                        RepresentationIdentifier="Body",
                        RepresentationType="Brep",
                        Items=items
                    )
                    
                    # Assign the representation to the product
                    ifcopenshell.api.run(
                        "geometry.assign_representation",
                        model,
                        product=product,
                        representation=body
                    )
                    
                    simplified += 1
                except Exception as e:
                    print(f"Error simplifying {product.is_a()} with brep: {str(e)}")
                    continue # Continues to the next product in the outer loop
        
        except Exception as e: # ADDED except block for the outer try
            print(f"Error processing product {product.id()} ({product.is_a()}) for simplification: {str(e)}")
            continue # Continue to the next product
    
    return simplified

def remove_empty_attributes(model):
    """Remove empty/default attributes by setting them to None using get_info()."""
    cleared = 0
    for entity in model:
        info = entity.get_info(include_identifier=False, recursive=False)
        for attr, value in info.items():
            if attr in ("id", "type"):
                continue
            if value in ("", None, 0, 0.0, "NOTDEFINED"):
                try:
                    if hasattr(entity, attr):
                        setattr(entity, attr, None)
                        cleared += 1
                except Exception as e:
                    print(f"Error clearing attribute '{attr}' on {entity}: {e}")
    return cleared

def remove_metadata(model):
    """Safer metadata removal - keeps at least one IfcOwnerHistory."""
    removed = 0
    owner_histories = model.by_type("IfcOwnerHistory")
    if owner_histories:
        for history in owner_histories[1:]:
            model.remove(history)
            removed += 1
    return removed

def remove_unused_spaces(model):
    spaces = model.by_type("IfcSpace")
    unused = []
    for space in spaces:
        if not any(
            ref for ref in model.get_inverse(space)
            if not ref.is_a(("IfcLocalPlacement", "IfcRelDefinesByProperties"))
        ):
            unused.append(space)
    for space in unused:
        model.remove(space)
    return len(unused)

def remove_unused_property_sets(model):
    psets = model.by_type("IfcPropertySet")
    removed = 0
    for pset in psets:
        if (not pset.HasProperties or len(pset.HasProperties) == 0) and not model.get_inverse(pset):
            try:
                for rel in model.get_inverse(pset):
                    if rel.is_a("IfcRelDefinesByProperties"):
                        model.remove(rel)
                model.remove(pset)
                removed += 1
            except Exception as e:
                print(f"Error removing property set: {e}")
    return removed

def remove_unused_materials(model):
    materials = model.by_type("IfcMaterial")
    removed = 0
    for material in materials:
        if not model.get_inverse(material):
            try:
                model.remove(material)
                removed += 1
            except Exception as e:
                print(f"Error removing material: {e}")
    return removed

def remove_unused_classifications(model):
    classifications = model.by_type("IfcClassificationReference")
    removed = 0
    for cls in classifications:
        if not model.get_inverse(cls):
            try:
                model.remove(cls)
                removed += 1
            except Exception as e:
                print(f"Error removing classification: {e}")
    return removed

def remove_small_elements(model, min_volume=0.001):
    removed = 0
    for element in model.by_type("IfcElement"):
        if element.Representation:
            try:
                vol = shape.get_volume(element)
                if vol and vol < min_volume:
                    model.remove(element)
                    removed += 1
            except Exception as e:
                print(f"Error checking volume: {e}")
    return removed

def remove_orphaned_entities(model):
    orphans = []
    for entity in model:
        if entity.is_a() in ["IfcProject", "IfcOwnerHistory"]:
            continue
        if not model.get_inverse(entity):
            orphans.append(entity)
    for entity in orphans:
        try:
            model.remove(entity)
        except Exception as e:
            print(f"Error removing orphan: {e}")
    return len(orphans)

def deduplicate_geometry(model):
    geometry_map = {}
    duplicates = 0
    
    # First pass: identify unique geometries
    for shape in model.by_type("IfcShapeRepresentation"):
        # Create a more robust hash key based on geometry properties
        try:
            # Get items in the shape representation
            items = shape.Items
            
            # Skip if no items
            if not items:
                continue
                
            # Create a hash key based on item types and properties
            key_parts = []
            for item in items:
                item_type = item.is_a()
                key_parts.append(item_type)
                
                # Add specific properties based on item type
                if item_type == "IfcExtrudedAreaSolid":
                    if hasattr(item, "Depth"):
                        key_parts.append(str(item.Depth))
                elif item_type == "IfcFacetedBrep":
                    if hasattr(item, "Outer") and hasattr(item.Outer, "CfsFaces"):
                        key_parts.append(str(len(item.Outer.CfsFaces)))
            
            # Create a hash key
            key = hash(tuple(key_parts))
            
            if key in geometry_map:
                geometry_map[key].append(shape)
            else:
                geometry_map[key] = [shape]
                
        except Exception as e:
            print(f"Error processing shape for deduplication: {e}")
            continue
    
    # Second pass: replace duplicates
    for key, shapes in geometry_map.items():
        if len(shapes) > 1:
            # Keep the first shape and replace others
            original_shape = shapes[0]
            for duplicate_shape in shapes[1:]:
                try:
                    for inverse in model.get_inverse(duplicate_shape):
                        ifcopenshell.util.element.replace_attribute(inverse, duplicate_shape, original_shape)
                    model.remove(duplicate_shape)
                    duplicates += 1
                except Exception as e:
                    print(f"Error deduplicating geometry: {e}")
    
    return duplicates

def flatten_spatial_structure(model):
    removed = 0
    for spatial in model.by_type("IfcSpatialStructureElement"):
        if not spatial.ContainsElements:
            try:
                model.remove(spatial)
                removed += 1
            except Exception as e:
                print(f"Error removing spatial element: {e}")
    return removed
