import argparse

import vault_converter

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Convert an Obsidian Vault into html files.")

    parser.add_argument("-in", "--in-vault", help="path to the Obsidian vault (should end with its name)", required=True)
    parser.add_argument("-out", "--out-path", help="output path of the converted html folder. Default is running directory", default="")

    args = parser.parse_args()

    path_to_vault = args.in_vault
    output_dir = args.out_path

    converter = vault_converter.Converter(path_to_vault, output_dir=output_dir)

    converter.convert_vault()
