import re
import os
from urllib.parse import quote
import shutil
import argparse
from pathlib import Path

template_path = 'base_template.html'


class Converter():

    def __init__(self, vault_path, output_dir):

        if not os.path.isdir(output_dir):
            raise ValueError(f"Fatal error: invalid output directory {output_dir}")

        self.output_dir = output_dir

        if not vault_path or not vault_path.strip():
            raise ValueError("Fatal error: vault path cannot be empty")
        
        self.path_to_vault = os.path.normpath(vault_path.strip())
        
        if not os.path.isdir(self.path_to_vault):
            raise ValueError(f"Fatal error: invalid vault path {self.path_to_vault}")
        
        self.vault_name = os.path.basename(self.path_to_vault)
        
        if not self.vault_name:  # Handle root directory case
            raise ValueError(f"Cannot determine vault name from path {self.path_to_vault}")
    
        """
        path_offset is the length of the path, name of the vault excluded
        This is useful for generating the the relative path of a file within the vault
        Example: 
        path_to_vault = "/path/to/myVault"
        vault_name = "myVault"
        path_offset = len("/path/to/myVault") - len("myVault) = 16 - 7 = 9
        path_to_vault_file = "/path/to/myVault/folder/subFolder/myFile.txt"
        path_within_vault = path_to_vault_file[path_offset:] = "myVault/folder/subFolder/myFile.txt"
        """
        self.path_offset = len(self.path_to_vault) - self.vault_name
        self.vault_files = self._generate_vault_files_list()

    def _replace_md_to_html(self, md_body):
        md_to_html_regex = [
            [r'\n\n', r'\n</p>\n\n<p>\n'],                                                      # Paragrap (empty line)
            [r'^# (.*)$', r'<h1>\1</h1>'],                                                      # Header 1 (# text)
            [r'^## (.*)$', r'<h2>\1</h2>'],                                                     # Header 2 (## text)
            [r'^### (.*)$', r'<h3>\1</h3>'],                                                    # Header 3 (### text)
            [r'^#### (.*)$', r'<h4>\1</h4>'],                                                   # Header 4 (#### text)
            [r'^##### (.*)$', r'<h5>\1</h5>'],                                                  # Header 5 (##### text)
            [r'^###### (.*)$', r'<h6>\1</h6>'],                                                 # Header 6 (###### text)
            [r'\*\*(.*?)\*\*', r'<b>\1</b>'],                                                   # Bold (**text**)
            [r'__(.*?)__', r'<b>\1</b>'],                                                       # Bold (__text__)
            [r'\* \*(.*?)\* \*', r'<i>\1</i>'],                                                 # Italic (* *text* *)
            [r'_ _(.*?)_ _', r'<i>\1</i>'],                                                     # Italic (_ _text_ _)
            [r'~~(.*?)~~', r'<del>\1</del>'],                                                   # Strike-through (~~text~~)
            [r'==(.*?)==', r'<mark>\1</mark>'],                                                 # Highlight (==text==)
            [r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>'],                                        # Bold + Italic (***text***)
            [r'___(.*?)___', r'<b><i>\1</i></b>'],                                              # Bold + Italic (___text___)
            [r'\[(.*?)\]\((.*?)\)', r'<a target="_blank" href="\2">\1</a>'],                    # External link ([display](external link))
            [r'(\n- .*(?:\n- .*)*)', r'\n<ul style="list-style-type:disc;">\1\n</ul>\n'],       # List <ul> (- elem1\n- elem2\n- elem3)
            [r'(\n\+ .*(?:\n\+ .*)*)', r'\n<ul style="list-style-type:disc;">\1\n</ul>\n'],     # List <ul> (+ elem1\n+ elem2\n+ elem3)
            [r'(\n\* .*(?:\n\* .*)*)', r'\n<ul style="list-style-type:disc;">\1\n</ul>\n'],     # List <ul> (* elem1\n* elem2\n* elem3)
            [r'(\n[0-9]+\. .*(?:\n[0-9]+\. .*)*)', r'\n<ol type="1">\1\n</ol>\n'],              # List <ol> (1. elem1\n2. elem2\n3. elem3)
            [r'(\n[0-9]+\) .*(?:\n[0-9]+\) .*)*)', r'\n<ol type="1">\1\n</ol>\n'],              # List <ol> (1) elem1\n2) elem2\n3) elem3)
            [r'\n- (.*)', r'\n  <li>\1</li>'],                                                  # List <il> (- elem1)
            [r'\n\+ (.*)', r'\n  <li>\1</li>'],                                                 # List <il> (+ elem1)
            [r'\n\* (.*)', r'\n  <li>\1</li>'],                                                 # List <il> (* elem1)
            [r'\n[0-9]+\. (.*)', r'\n  <li>\1</li>'],                                           # List <il> (1. elem1)
            [r'\n[0-9]+\) (.*)', r'\n  <li>\1</li>'],                                           # List <il> (1) elem1)
            [r'^\*{3,}|_{3,}|-{3,}$', r'\n  </p>\n<hr>\n<p>']                                   # Horizontal line (***+ OR ___+ OR ---+)
        ]
        for mapping in md_to_html_regex:
            md_body = re.sub(mapping[0], mapping[1], md_body, flags=re.MULTILINE)
        return md_body


    def _replace_obsidian_internal_links(self, md_body):
        matches = list(set(re.findall(r'\[\[.+?\]\]', md_body)))

        for match in matches:
            print(f"Starting internal link conversion: {match}")
            og_match = match
            match = match[2:-2]

            link_display = ''
            if '|' in match:
                match, link_display = match.split('|', 1)
            else: 
                link_display = match[match.rfind('/')+1:]

            # For path building, we have 3 scenarios (see assumption above):
            # 1) the link contains os.sep, in which case we have its full relative path
            # 2) the link does not contain os.sep, because the file is in the root of the vault
            # 3) the link does not contain os.sep, because it is the only file in the entire vault with that name

            # Scenario 1 or 2
            if os.sep in match or os.path.exists(os.path.join(self.path_to_vault, match + '.md')):
                link_path = '/' + quote(f"{self.vault_name}/{match.replace(os.sep, '/')}.html")
            # Scenario 3
            else:
                link_path = '/' + quote(self._get_file_path_in_vault(match).replace('.md', '.html').replace(os.sep, '/'))

            md_body = md_body.replace(og_match, f'<a href="{link_path}">{link_display}</a>')

        return md_body



    # def truncated_vault_path(file_path):
    #     if file_path.startswith(vault_name):
    #         return file_path
    #     folder_name = re.findall(r'[\/\\]'+vault_name+r'[\/\\]', file_path)

    def _generate_vault_files_list(self):
        vault_files = []
        for root, dirs, files in os.walk(self.path_to_vault):
            for file in files:
                vault_files.append(os.path.join(root, file)[self.path_offset:])
        return vault_files
    

    def _replace_obsidian_internal_links(self, md_body):
        matches = list(set(re.findall(r'\[\[.+?\]\]', md_body)))

        for link_match in matches:
            print(f"Starting internal link conversion: {link_match}")
            # full_link_match is surrounded by double square brackets, like [[_my_link_]], link_match is not
            full_link_match = link_match
            link_match = link_match[2:-2]

            link_display = ''
            if '|' in link_match:
                link_match, link_display = link_match.split('|', 1)
            else: 
                link_display = link_match[link_match.rfind('/')+1:]

            # For path building, we have 3 scenarios:
            # 1) the link contains os.sep, in which case we have its full relative path
            # 2) the link does not contain os.sep, because the file is in the root of the vault
            # 3) the link does not contain os.sep, because it is the only file in the entire vault with that name

            # Scenario 1 or 2
            if os.sep in link_match or os.path.exists(os.path.join(self.path_to_vault, link_match + '.md')):
                link_path = '/' + quote(self.vault_name + '/' + link_match.replace(os.sep, '/') + '.html')
            # Scenario 3
            else:
                link_path = '/' + quote(self._get_file_path_in_vault(link_match).replace('.md', '.html').replace(os.sep, '/'))

            md_body = md_body.replace(full_link_match, f'<a href="{link_path}">{link_display}</a>')

        return md_body


    def _get_file_path_in_vault(self, file_name):
        for vault_file in self.vault_files:
            if vault_file.endswith(file_name) or vault_file.endswith(file_name + '.md'):
                return vault_file
        print(f"Fatal error: could not resolve link for {file_name}")
        exit()

    def _get_html_file_from_md(self, md_file_path):
        # remove the final .md of the file
        name = os.path.basename(md_file_path)[:-3]
        print(f"name found: {name}")
        with open(md_file_path, "r") as fp:
            md_data = fp.read()
        md_data = md_data.replace('\n', '<br>\n')
        md_data = self._replace_md_to_html(md_data)
        md_data = self._replace_obsidian_internal_links(md_data)
        with open(template_path, 'r') as fp:
            template = fp.read()
        return template.replace('{PAGE_TITLE}', name).replace('{PAGE_HEADER}', name).replace('{MAIN_BODY}', md_data)

    def convert_vault(self):
        for root, dirs, files in os.walk(self.path_to_vault):
            # skip the conversion of the .obsidian folder and its content
            if '.obsidian' in root:
                continue
            target_dir = os.path.join(self.output_dir, root[self.path_offset:])
            if not os.path.exists(target_dir):
                os.mkdir(target_dir)
            for file in files:
                if file.endswith('.md'):
                    md_to_write = self._get_html_file_from_md(os.path.join(root, file))
                    with open(os.path.join(target_dir, file).replace('.md', '.html'), "w") as fw:
                        fw.write(md_to_write)
                else:
                    shutil.copy(os.path.join(root, file), os.path.join(target_dir, file))
        print("\n\nJob complete!")



