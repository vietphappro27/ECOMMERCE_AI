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
    
    # Check if there are style blocks
    if '<style>' in content:
        # Replace all style blocks with link tag
        # Find the first style tag position
        style_start = content.find('<style>')
        style_end = content.find('</style>') + len('</style>')
        
        if style_start >= 0 and style_end > style_start:
            # Get the head section
            head_start = content.find('<head>')
            head_end = content.find('</head>')
            
            if head_start >= 0 and head_end > head_start:
                # Remove all style blocks
                new_content = re.sub(r'<style>.*?</style>', '', content, flags=re.DOTALL)
                
                # Add link tag before </head>
                css_link = f'    <link rel="stylesheet" href="{{% static "css/{css_name}.css" %}}">\n    '
                new_content = new_content.replace('    </head>', f'{css_link}</head>')
                
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Updated {html_file}')
            else:
                print(f'{html_file}: Could not find head section')
    else:
        print(f'{html_file}: No styles to remove')

print('\nHTML cleanup complete!')
