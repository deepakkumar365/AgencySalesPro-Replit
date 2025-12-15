from main import app
from extensions import db
from models import Product, Agency, ProductAgency, User

def test_product_search():
    with app.app_context():
        print("--- Diagnostic: Product Availability ---")
        
        # 1. List all Agencies
        agencies = Agency.query.all()
        print(f"Total Agencies: {len(agencies)}")
        for a in agencies:
            print(f"  Agency ID: {a.id}, Name: {a.name}")
            
        # 2. List a few Products (Global)
        products = Product.query.filter_by(is_active=True).limit(5).all()
        print(f"\nTotal Active Active Products (Limit 5):")
        for p in products:
            print(f"  ID: {p.id}, Name: {p.name}, SKU: {p.sku}")
            
        # 3. Check Product-Agency Mappings
        print(f"\nProduct-Agency Mappings (Limit 10):")
        mappings = ProductAgency.query.filter_by(is_active=True).limit(10).all()
        for m in mappings:
            print(f"  ProdID: {m.product_id} <-> AgencyID: {m.agency_id} | Price: {m.sell_price}")

        # 4. Simulate Search Logic (Match routes.py)
        # Assume we are searching for a term like "a" or the first product's name
        search_term = products[0].name[:3] if products else "test"
        print(f"\n--- Testing Search Logic for term: '{search_term}' ---")
        
        # Test for specific agency (e.g., first agency found)
        test_agency_id = agencies[0].id if agencies else 1
        print(f"Testing context: Agency ID {test_agency_id}")
        
        # LOGIC FROM ROUTES.PY
        # Non-super-admin logic (Strict Join)
        try:
            strict_query = db.session.query(Product).join(
                ProductAgency,
                db.and_(
                    ProductAgency.product_id == Product.id,
                    ProductAgency.agency_id == test_agency_id,
                    ProductAgency.is_active == True
                )
            ).filter(Product.is_active == True)
            
            like = f"%{search_term}%"
            strict_query = strict_query.filter(db.or_(
                Product.name.ilike(like),
                Product.sku.ilike(like),
                ProductAgency.display_name.ilike(like)
            ))
            
            results = strict_query.all()
            print(f"Strict Search (Non-Admin) Result Count: {len(results)}")
            for r in results:
                print(f"  Found: {r.name}")
        except Exception as e:
            print(f"Strict search failed: {e}")

        # Super-admin logic (Outer Join)
        try:
            outer_query = db.session.query(Product).outerjoin(
                ProductAgency,
                db.and_(
                    ProductAgency.product_id == Product.id,
                    ProductAgency.agency_id == test_agency_id
                )
            ).filter(Product.is_active == True)
            
            outer_query = outer_query.filter(db.or_(
                Product.name.ilike(like),
                Product.sku.ilike(like),
                ProductAgency.display_name.ilike(like)
            ))
            
            results_outer = outer_query.all()
            print(f"Outer Search (Admin) Result Count: {len(results_outer)}")
        except Exception as e:
             print(f"Outer search failed: {e}")

if __name__ == "__main__":
    test_product_search()
