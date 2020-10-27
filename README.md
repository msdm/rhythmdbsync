# rhythmdbsync

A tool to import ID3 ratings (Popularities) to Rhythmbox database, and export
the ratings from the database to the actual files.

## Requirements

* Python V3.6 or later
* Python eyed3 package
    
## Usage

    rhythmdbsync [options] import
        Import the ID3 ratings from files to the database. If a POPM ID3 frame
        exists in the file metadata with the 'Rhythmbox' as its email string,
        it will be imported. Otherwise, any other POPM frame set by other
        applications will be imported.
        
    rhythmdbsync [options] export
        Export the ratings from the database to the actual files.
    
## Options

    -h, --help
        Show this page.
        
    -i <file>, --input-file=<file>
        Specify the input Rhythmbox database file. If not provided,
        ~/.local/share/rhythmdb.xml will be used by default.
        
    -o <file>, --output-file=<file>
        Specify the output Rhythmbox database file. If not provided, the input
        file will be overwritten. This option is only used for imporing.
        
    --force
        By default, the ratings will not be imported/exported if a rating is
        already exists in the destination for that specific item. Providing
        --force option will cause to import/exports the ratings regardless of
        the existence of a rating in the destination.
        
    --log-file=<file>
        The file that the logs will be stored in it. If not provided, logging
        will be disabled.
        
    --log-level=[critical|error|warning|info|debug]
        The logging level. The default level is "warning".
        
    --dry
        Providing this option will not save the import/export result in the
        files. This is useful to evaluate what will happen after the actual
        import/export.
