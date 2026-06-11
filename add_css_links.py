import re
import os

html_files = [
    ('api-gateway/app/templates/app/customer_dashboard.html', 'customer_dashboard'),
    ('api-gateway/app/templates/app/customer_cart.html', 'customer_cart'),
    ('api-gateway/app/templates/app/customer_order.html', 'customer_order'),
    ('api-gateway/app/templates/app/login.html', 'login'),
    ('api-gateway/app/templates/app/register.html', 'register'),
    ('api-gateway/app/templates/app/staff_dashboard.html', 'staff_dashboard')
]

for html_file, css_name in html_files:
    if not os.path.exists(html_file):
        print(f'Skipping {html_file}: not found')
        continue
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if link tag already exists
    if f'css/{css_name}.css' in content:
        print(f'{html_file}: CSS link already exists')
        continue
    
    # Find the closing head tag
    if '</head>' in content:
        # Create CSS link
        css_link = f'    <link rel="stylesheet" href="{{% static "css/{css_name}.css" %}}">\n'
        
        # Insert before </head>
        new_content = content.replace('</head>', css_link + '</head>')
        
        # Add {% load static %} at the very beginning after DOCTYPE
        if '{% load static %}' not in new_content:
            # Find the first line after <!DOCTYPE html>
            match = re.search(r'(<!DOCTYPE html>\n)', new_content)
            if match:
                new_content = new_content.replace(match.group(1), match.group(1) + '{% load static %}\n')
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {html_file}')
    else:
        print(f'{html_file}: Could not find </head>')

print('\nHTML update complete!')
