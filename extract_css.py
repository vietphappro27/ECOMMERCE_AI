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

css_dir = 'api-gateway/app/static/css'

for html_file, css_name in html_files:
    if not os.path.exists(html_file):
        print(f'Skipping {html_file}: not found')
        continue
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all style blocks
    style_blocks = re.findall(r'<style>(.*?)</style>', content, re.DOTALL)
    
    if style_blocks:
        css_file_path = os.path.join(css_dir, f'{css_name}.css')
        with open(css_file_path, 'w', encoding='utf-8') as css_file:
            for i, block in enumerate(style_blocks):
                if i > 0:
                    css_file.write('\n\n')
                css_file.write(block)
        print(f'Created {css_file_path} with {len(style_blocks)} style block(s)')
    else:
        print(f'{html_file}: No styles found')

print('\nCSS extraction complete!')
