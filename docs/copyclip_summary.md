# CopyClip Database Analysis Summary

## Database Location
- **Primary DB**: `/Users/simfish/Library/Containers/com.fiplab.clipboard/Data/Library/Application Support/CopyClip/copyclip.sqlite`
- **Secondary DB**: `/Users/simfish/Library/Containers/com.fiplab.copyclip2/Data/Library/Application Support/CopyClip/copyclip.sqlite`

## Key Statistics

### Overall
- **Total clipboard entries**: 9,999
- **Total characters**: 6,869,250
- **Average entry length**: 687.0 characters
- **Shortest entry**: 1 character
- **Longest entry**: 178,777 characters

### Word Analysis
- **Total unique words**: 1,563
- **Total word occurrences**: 4,692

## Top 50 Most Common Words

| Word | Frequency |
|------|-----------|
| the | 195 times |
| a | 73 times |
| to | 67 times |
| is | 55 times |
| entropy | 54 times |
| curvature | 52 times |
| s | 50 times |
| t | 46 times |
| that | 44 times |
| and | 43 times |
| of | 42 times |
| directions | 41 times |
| you | 40 times |
| fisher | 40 times |
| in | 36 times |
| with | 30 times |
| it | 28 times |
| for | 26 times |
| memorization | 24 times |
| this | 24 times |
| top | 23 times |
| k | 23 times |
| information | 22 times |
| x | 20 times |
| high | 19 times |
| sinkhorn | 19 times |
| https | 18 times |
| on | 18 times |
| or | 18 times |
| no | 18 times |

## Notable Technical Terms

Based on the word frequency, your clipboard contains significant content related to:

1. **Machine Learning / AI**: entropy, curvature, fisher, memorization, regularization, loss, spectrum
2. **Mathematics**: sinkhorn (optimal transport), information, directions, structure
3. **Web Content**: https, com, www (URLs)

## Recent Clipboard Activity

The most recent entries include:
- Slack authentication tokens
- JavaScript code snippets
- URLs to various websites (YouTube, LessWrong, Signal groups, etc.)
- Technical discussions about AI/ML concepts
- Location addresses in San Francisco
- Personal communications

## Database Schema

### ZCLIPPING Table (Main clipboard data)
- `Z_PK`: Primary key
- `ZCONTENTS`: The actual clipboard text content
- `ZDATERECORDED`: Timestamp (Core Data format, reference date 2001-01-01)
- `ZSOURCE`: Foreign key to ZSOURCEAPP table
- `ZTYPE`: Type of clipboard content (e.g., NSStringPboardType)
- `ZDISPLAYNAME`: Display name for the entry
- `ZATTRIBUTEDCONTENTS`: Binary data with formatting

### ZSOURCEAPP Table
- Tracks which application the clipboard content came from
- Common sources: Google Chrome, Comet, ChatGPT, Signal, Windsurf, Ghostty

## Files Generated

1. `analyze_copyclip.py` - Full database structure analyzer
2. `extract_copyclip_text.py` - Text content extractor with word frequency analysis
3. `inspect_copyclip_schema.py` - Schema inspection tool
4. `copyclip_analysis.txt` - Full analysis output
5. `copyclip_summary.md` - This summary document
