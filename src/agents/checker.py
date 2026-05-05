"""
Checker Agent
Validates translation quality and glossary consistency.
"""

import re
import logging
from typing import List, Dict, Any

from src.memory.memory_manager import MemoryManager
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class Checker(BaseAgent):
    """
    Checks translation for:
    - Glossary consistency
    - Character name consistency
    - Markdown formatting preservation
    - Basic quality indicators
    """

    def __init__(self, memory_manager: MemoryManager = None, config: dict = None):
        super().__init__(memory_manager=memory_manager, config=config)
        self.memory = memory_manager

    def check_glossary_consistency(self, text: str) -> List[Dict[str, str]]:
        """
        Check if glossary terms are used consistently.
        
        Two checks:
        1. Untranslated terms: Chinese source appears verbatim in Myanmar text
        2. Target spelling check: for verified character/place names where
           the source is NOT in the text (was translated), flag if the
           approved target spelling is also missing (= wrong variant used)
        
        Returns list of issues with 'term', 'expected', 'found'.
        """
        issues = []

        # Get all glossary terms
        terms = self.memory.get_all_terms()

        for term in terms:
            source = term.get('source') or term.get('source_term', '')
            target = term.get('target') or term.get('target_term', '')
            category = term.get('category', '')

            if not source or not target or len(source) < 2:
                continue

            # Check 1: Source term leaked untranslated
            if source in text:
                issues.append({
                    'type': 'untranslated_term',
                    'term': source,
                    'expected': target,
                    'found': source
                })
            # Check 2: For verified character/place names, verify target appears
            elif term.get('verified') and category in ('character', 'place'):
                if target not in text:
                    issues.append({
                        'type': 'target_missing',
                        'term': source,
                        'expected': target,
                        'found': '?'
                    })

        return issues

    def check_markdown_formatting(self, original: str, translated: str) -> List[str]:
        """
        Check if markdown formatting is preserved.
        
        Returns list of formatting issues.
        """
        issues = []

        # Count headers in original
        original_headers = len(re.findall(r'^#+ ', original, re.MULTILINE))
        translated_headers = len(re.findall(r'^#+ ', translated, re.MULTILINE))

        if original_headers != translated_headers:
            issues.append(
                f"Header count mismatch: {original_headers} -> {translated_headers}"
            )

        # Count bold/italic markers
        original_bold = original.count('**')
        translated_bold = translated.count('**')

        if original_bold != translated_bold:
            issues.append(
                f"Bold marker count mismatch: {original_bold} -> {translated_bold}"
            )

        return issues

    def check_myanmar_unicode(self, text: str) -> List[str]:
        """
        Check for Myanmar Unicode issues.
        
        Returns list of Unicode issues.
        """
        issues = []

        # Check for common Unicode problems
        if '�' in text:
            issues.append("Contains replacement character (�)")

        # Check for mixed scripts (Myanmar range: U+1000-U+109F)
        # Allow Myanmar, punctuation, whitespace, digits
        _MYANMAR = r'\u1000-\u109F'
        _PUNCT = r'\u2000-\u206F\u3000-\u303F'
        _ALLOWED = r'\s\d.,!?;:\-\'"()[]{}'
        non_myanmar = re.findall(r'[^\u1000-\u109F\u2000-\u206F\u3000-\u303F\s\d.,!?;:\-\'"()[]{}]', text)
        if len(non_myanmar) > len(text) * 0.3:  # More than 30% non-Myanmar
            issues.append(f"High non-Myanmar character ratio: {len(non_myanmar)} chars")

        return issues

    def check_foreign_characters(self, text: str) -> List[Dict[str, str]]:
        """
        Check for foreign script leakage (Korean, Japanese, Chinese, etc.)
        except Bengali which is handled separately.
        
        Returns list of issues found.
        """
        issues = []
        
        # Korean Hangul (U+AC00-U+D7AF, U+1100-U+11FF, U+3130-U+318F)
        korean_chars = re.findall(r'[ᄀ-ᇿᰀ-ᱏ]', text)
        if korean_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Korean',
                'found': ''.join(korean_chars[:10]),  # First 10 chars
                'expected': 'Translate to Burmese'
            })
        
        # Japanese Katakana (U+30A0-U+30FF)
        japanese_chars = re.findall(r'[Ꭰ-Ꮟ]', text)
        if japanese_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Japanese',
                'found': ''.join(japanese_chars[:10]),
                'expected': 'Translate to Burmese'
            })
        
        # Chinese characters (already checked by LANGUAGE_GUARD but double-check)
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        if chinese_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Chinese',
                'found': ''.join(chinese_chars[:10]),
                'expected': 'Translate to Burmese'
            })
        
        return issues

    def check_incomplete_sentences(self, text: str) -> List[Dict[str, str]]:
        """
        Check for incomplete sentences (abrupt cutoffs).
        
        Looks for sentences that end mid-word or without proper ending.
        """
        issues = []
        
        # Split by sentence endings
        sentences = re.split(r'[။၊!?\n]+', text)
        
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if not sent:
                continue
                
            # Check if sentence ends abruptly (no proper ending, just cut off)
            # Pattern: ends with consonant + virama (္) without final character
            if re.search(r'[က-အ်ျြှၚၛၜၝၡၥၦၧၨၩၪၫၬၭၮၯၰၱၲၳၴၵၶၷၸၹၺၻၼၽၾၿႀႁႂႃႄႅႆႇႈႉႊႋႌႍႎႏ႐႑႒႓႔႕႖႗႘႙ႚႛႜႝ႞႟ႠႡႢႣႤႥႦႧႨႩႪႫႬႭႮႯႰႱႲႳႴႵႶႷႸႹႺႻႼႽႾႿჀჁჂჃჄჅ჆Ⴧ჈჉჊჋჌Ⴭ჎჏აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰჱჲჳჴჵჶჷჸჹჺ჻ჼჽჾჿᄀᄁᄂᄃᄄᄅᄆᄇᄈᄉᄊᄋᄌᄍᄎᄏᄐᄑᄒᄓᄔᄕᄖᄗᄘᄙᄚᄛᄜᄝᄞᄟᄠᄡᄢᄣᄤᄥᄦᄧᄨᄩᄪᄫᄬᄭᄮᄯᄰᄱᄲᄳᄴᄵᄶᄷᄸᄹᄺᄻᄼᄽᄾᄿᅀᅁᅂᅃᅄᅅᅆᅇᅈᅉᅊᅋᅌᅍᅎᅏᅐᅑᅒᅓᅔᅕᅖᅗᅘᅙᅚᅛᅜᅝᅞᅟᅠᅡᅢᅣᅤᅥᅦᅧᅨᅩᅪᅫᅬᅭᅮᅯᅰᅱᅲᅳᅴᅵᅶᅷᅸᅹᅺᅻᅼᅽᅾᅿᆀᆁᆂᆃᆄᆅᆆᆇᆈᆉᆊᆋᆌᆍᆎᆏᆐᆑᆒᆓᆔᆕᆖᆗᆘᆙᆚᆛᆜᆝᆞᆟᆠᆡᆢᆣᆤᆥᆦᆧᆨᆩᆪᆫᆬᆭᆮᆯᆰᆱᆲᆳᆴᆵᆶᆷᆸᆹᆺᆻᆼᆽᆾᆿᇀᇁᇂᇃᇄᇅᇆᇇᇈᇉᇊᇋᇌᇍᇎᇏᇐᇑᇒᇓᇔᇕᇖᇗᇘᇙᇚᇛᇜᇝᇞᇟᇠᇡᇢᇣᇤᇥᇦᇧᇨᇩᇪᇫᇬᇭᇮᇯᇰᇱᇲᇳᇴᇵᇶᇷᇸᇹᇺᇻᇼᇽᇾᇿሀሁሂሃሄህሆሇለሉሊላሌልሎሏሐሑሒሓሔሕሖሗመሙሚማሜምሞሟሠሡሢሣሤሥሦሧረሩሪራሬርሮሯሰሱሲሳሴስሶሷሸሹሺሻሼሽሾሿቀቁቂቃቄቅቆቇቈ቉ቊቋቌቍ቎቏ቐቑቒቓቔቕቖ቗ቘ቙ቚቛቜቝ቞቟በቡቢባቤብቦቧቨቩቪቫቬቭቮቯተቱቲታቴትቶቷቸቹቺቻቼችቾቿኀኁኂኃኄኅኆኇኈ኉ኊኋኌኍ኎኏ነኑኒናኔንኖኗኘኙኚኛኜኝኞኟአኡኢኣኤእኦኧከኩኪካኬክኮኯኰ኱ኲኳኴኵ኶኷ኸኹኺኻኼኽኾ኿ዀ዁ዂዃዄዅ዆዇ወዉዊዋዌውዎዏዐዑዒዓዔዕዖ዗ዘዙዚዛዜዝዞዟዠዡዢዣዤዥዦዧየዩዪያዬይዮዯደዱዲዳዴድዶዷዸዹዺዻዼዽዾዿጀጁጂጃጄጅጆጇገጉጊጋጌግጎጏጐ጑ጒጓጔጕ጖጗ጘጙጚጛጜጝጞጟጠጡጢጣጤጥጦጧጨጩጪጫጬጭጮጯጰጱጲጳጴጵጶጷጸጹጺጻጼጽጾጿፀፁፂፃፄፅፆፇፈፉፊፋፌፍፎፏፐፑፒፓፔፕፖፗፘፙፚ፛፜፝፞፟፠፡።፣፤፥፦፧፨፩፪፫፬፭፮፯፰፱፲፳፴፵፶፷፸፹፺፻፼ᎀᎁᎂᎃᎄᎅᎆᎇᎈᎉᎊᎋᎌᎍᎎᎏ᎐᎑᎒᎓᎔᎕᎖᎗᎘᎙]+$', sent):
                # Check if it's too short to be a valid sentence ending
                if len(sent) < 10 and not re.search(r'[။၊!?]$', sent):
                    issues.append({
                        'type': 'incomplete_sentence',
                        'position': i,
                        'text': sent[:30] + '...' if len(sent) > 30 else sent
                    })
        
        return issues

    def calculate_quality_score(self, text: str) -> float:
        """
        Calculate basic quality score (0-100).
        
        Based on:
        - Myanmar character ratio
        - Sentence count
        - Basic formatting
        """
        score = 100.0

        # Check Myanmar content ratio
        total_chars = len(text)
        myanmar_chars = len(re.findall(r'[\u1000-\u109F]', text))

        if total_chars > 0:
            myanmar_ratio = myanmar_chars / total_chars
            if myanmar_ratio < 0.5:
                score -= 30  # Too little Myanmar content
            elif myanmar_ratio < 0.7:
                score -= 15

        # Check for empty or very short output
        if total_chars < 50:
            score -= 50

        # Check for obvious error markers
        if '[ERROR' in text or '[TRANSLATION ERROR' in text:
            score -= 40

        return max(0.0, score)

    def check_chapter(
        self,
        original: str,
        translated: str
    ) -> Dict[str, Any]:
        """
        Run all checks on a chapter translation.
        
        Args:
            original: Original Chinese text
            translated: Myanmar translation
            
        Returns:
            Dict with 'passed', 'score', and 'issues'
        """
        issues = []

        # Glossary consistency
        glossary_issues = self.check_glossary_consistency(translated)
        issues.extend([
            f"Glossary: {i['term']} should be '{i['expected']}'"
            for i in glossary_issues
        ])

        # Markdown formatting
        format_issues = self.check_markdown_formatting(original, translated)
        issues.extend(format_issues)

        # Unicode issues
        unicode_issues = self.check_myanmar_unicode(translated)
        issues.extend(unicode_issues)

        # Foreign character leakage check
        foreign_issues_count = 0
        try:
            foreign_issues = self.check_foreign_characters(translated)
            foreign_issues_count = len(foreign_issues)
            issues.extend([
                f"Foreign ({i['language']}): {i['found'][:20]}..."
                for i in foreign_issues if i.get('found')
            ])
        except Exception as e:
            logger.warning(f"Foreign char check failed: {e}")

        # Incomplete sentences check
        incomplete_issues_count = 0
        try:
            incomplete_issues = self.check_incomplete_sentences(translated)
            incomplete_issues_count = len(incomplete_issues)
            issues.extend([
                f"Incomplete sentence: {i['text'][:30]}..."
                for i in incomplete_issues
            ])
        except Exception as e:
            logger.warning(f"Incomplete sentence check failed: {e}")

        # Calculate score
        score = self.calculate_quality_score(translated)

        # Adjust score for issues
        score -= len(issues) * 5
        score = max(0.0, score)

        return {
            'passed': score >= 70 and len(issues) < 5,
            'score': score,
            'issues': issues,
            'glossary_issues': len(glossary_issues),
            'format_issues': len(format_issues),
            'unicode_issues': len(unicode_issues),
            'foreign_issues': foreign_issues_count,
            'incomplete_issues': incomplete_issues_count
        }

    def generate_report(self, chapter_num: int, result: Dict) -> str:
        """Generate human-readable check report."""
        lines = [
            f"Chapter {chapter_num} Quality Check",
            "=" * 40,
            f"Score: {result['score']:.1f}/100",
            f"Status: {'✓ PASSED' if result['passed'] else '✗ FAILED'}",
            f"Total Issues: {len(result['issues'])}",
            ""
        ]

        if result['issues']:
            lines.append("Issues Found:")
            for issue in result['issues'][:10]:  # Show first 10
                lines.append(f"  - {issue}")
            if len(result['issues']) > 10:
                lines.append(f"  ... and {len(result['issues']) - 10} more")

        return "\n".join(lines)
