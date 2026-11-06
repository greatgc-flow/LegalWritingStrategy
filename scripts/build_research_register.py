# WARNING: historical V4 seed generator. Do not run this in V4.1 to overwrite the audited register.
# Source-of-truth: references/research_register.csv. To update, validate DOI, year, title, limits and edit CSV with diff.
import csv
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=[
('L01','2022','Martínez; Mollica; Gibson','Poor writing, not specialized concepts, drives processing difficulty in legal language','10.1016/j.cognition.2022.105070','legal language','A','metadata_abstract','English legal texts; no Korean case outcome causal inference'),
('L02','2023','Martínez; Mollica; Gibson','Even lawyers do not like legalese','10.1073/pnas.2302672120','legal readability','A','metadata_abstract','Preregistered lawyer experiments on English contracts'),
('L03','2024','Martínez; Mollica; Gibson','Even laypeople use legalese','10.1073/pnas.2405564121','legal wording','A','metadata_abstract','English legislation writing tasks'),
('L04','2024','Martínez; Mollica; Gibson','So much for plain language','10.1037/xge0001572','legal language corpus','A','metadata_abstract','US laws; corpus measure not Korean pleadings'),
('L05','2024','Yonathan A. Arbel','The readability of contracts: Big data analysis','10.1111/jels.12400','counterevidence','A','metadata_abstract','Readability score not comprehension or validity'),
('L06','2025','Guitton et al.','Controlled Language Increases Comprehension of Law for People','10.1145/3711128','plain legal language','A','metadata_only','Check original experimental procedure before quoting estimates'),
('L07','2025','van der Bruggen; Pander Maat','Dutch judicial decisions plain-language experiment','10.5117/TVT2025.02.001.BRUG','structure','A','metadata_only','Dutch decision not Korean submission'),
('L08','2023','Prinz-Weiß; König','Caption it! The impact of headings on learning from texts','10.1002/acp.4076','headings','B','metadata_only','Education context not judicial outcome'),
('L09','1986','Petty; Cacioppo','Elaboration Likelihood Model of Persuasion','10.1016/S0065-2601(08)60214-2','persuasion','B','metadata_only','General psychology, not prosecutorial manipulation'),
('L10','1991','Allen','Meta-analysis on one- versus two-sided messages','10.1080/10570319109374395','counterargument','B','metadata_only','Average effect and moderators not verified here'),
('L11','2025','Ma; Nan','Narrative persuasion systematic review','10.1093/anncom/wlaf007','narrative','B','metadata_only','General communication, context-specific'),
('L12','2025','Kim; Chen','Gain-loss framing research','10.1093/joc/jqaf002','framing','B','metadata_only','Journal article; exact domain/estimates to recheck'),
('L13','2026','Markowitz; Sun','Computational mapping of persuasion research','10.1111/spc3.70171','persuasion mapping','B','metadata_only','Publication patterns not effects'),
('L14','2025','van Aaken; Sarel','Legal framing and proportionality judgments','10.1177/2755323X251380088','legal decision framing','A','metadata_only','Specific proportionality task'),
('L15','2022','Noetel et al.','Multimedia design review of reviews','10.3102/00346543211052329','visual design','B','metadata_only','Learning context'),
('L16','2024','Richard E. Mayer','Cognitive theory of multimedia learning','10.1007/s10648-023-09842-1','cognitive load','B','metadata_only','Indirect legal-document transfer'),
('L17','2024','Ok; Lee; Jung','Analyzing the readability of Korean serif and sans serif fonts using eye-tracking data','10.5626/KTCP.2024.30.6.264','Korean typography','B','metadata_abstract','n=58; specific fonts, not universal font ranking'),
('L18','2026','TandF study authors','Just the font types? Effects of serif vs sans-serif font types on text comprehension in screen vs paper reading','10.1080/0144929X.2026.2678378','typography','B','metadata_abstract','n=132 English passage and specific font pairs'),
('L19','2026','Wszołek et al.','The Importance of Visualization Methods and Information Presentation in the Reception of a Legal Document','10.18848/2325-1581/CGP/A174','legal visual emphasis','A','metadata_abstract','Non-law participants; syntax moderates signals'),
('L20','2026','Romano; Rose; Sotis','Color in contract terms','10.1086/742145','contract visual emphasis','A','metadata_only','Contract terms; not court submissions'),
('L21','2021','McLachlan; Webley','Legal visualization research','10.1177/14738716211012608','legal visuals','B','metadata_only','Legal design not causal court decision'),
('L22','2024','Dahl et al.','Large Legal Fictions','10.1093/jla/laae003','legal AI hallucinations','A','metadata_only','Model generations and dataset time-bound'),
('L23','2025','Magesh et al.','Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools','10.1111/jels.12413','legal AI','A','metadata_abstract','17-33 percent in sampled proprietary tools and evaluation conditions'),
('L24','2024','Kamoi et al.','When Can LLMs Actually Correct Their Own Mistakes?','10.1162/tacl_a_00713','AI validation','B','metadata_abstract','Self-correction depends on reliable external feedback'),
('L25','2024','Liu et al.','Lost in the Middle: How Language Models Use Long Contexts','10.1162/tacl_a_00638','context cost/recall','B','metadata_abstract','Model & task dependent, not every 2026 model'),
('L26','2024','Wu et al.','Large Language Models Can Self-Correct with Key Condition Verification','10.18653/v1/2024.emnlp-main.714','structured validation','B','metadata_abstract','Specific arithmetic and QA tasks'),
('L27','2024','Pan et al.','Automatically Correcting Large Language Models','10.1162/tacl_a_00660','AI feedback','B','metadata_abstract','Survey of varied tasks and tools'),
('L28','2026','IEEE Access authors','A Reusable Prompting Framework for Applying Large Language Models to Legal Tasks','10.1109/ACCESS.2026.3650941','legal prompts','A','metadata_abstract','Specific task/model performance, not court outcomes'),
('L29','2025/2026','Kelsall et al.','A rapid evidence review of evaluation techniques for large language models in legal use cases','10.1007/s00146-025-02741-9','legal AI evaluation','A','full_text_page','Rapid review; 140 studies; task/evaluation gap'),
('L30','2024','Huang et al.','Large Language Models Cannot Self-Correct Reasoning Yet','','AI self-correction','B','metadata_abstract','ICLR; no external feedback'),
('L31','2024','Gou et al.','CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing','','AI tool-assisted correction','B','metadata_abstract','ICLR; improvement in benchmark tasks'),
('L32','2026','Linna; Linna','Legal reasoning challenges','10.1007/s44163-026-00902-3','legal AI','B','metadata_only','Conceptual, factual claims to inspect'),
('L33','2026','Choi','Large language models as judges and prompt sensitivity','10.1111/jels.70041','decision bias','A','metadata_only','Research task, not prediction of real judges'),
('L34','2026','Pulvino; Sutton; Naddeo','AI legal analysis and prosecutorial bias','10.52214/stlr.v27i1.14543','decision bias','A','metadata_only','Further evaluation of study sample needed'),
('L35','2026','Shi et al.','Rubric benchmark for legal practice','','legal QA','A','metadata_only','https://aclanthology.org/2026.acl-long.458/'),
('L36','2025','Xu; Petty','Two-sided misinformation messages','10.1177/23794607251382992','two-sided communication','B','metadata_only','Misinformation context, not criminal briefs'),
('L37','2024','Porter; Wood','Factual corrections and belief','10.1016/j.copsyc.2023.101715','cognitive biases','B','metadata_only','Correction messages, not court'),
('L38','2024','Prike; Ecker','Misinformation corrections','10.1016/j.copsyc.2023.101712','cognitive biases','B','metadata_only','Correction messages, not legal proof'),
('L39','2025','Schloss','Visualization perception and cognition','10.1146/annurev-vision-110323-110009','chart perception','B','metadata_only','General perception'),
('L40','2025','Chang et al.','Argument visualization','10.3389/feduc.2025.1672105','argument mapping','B','metadata_only','Educational test, not judges'),
]
p=root/'references/research_register_seed_v4.csv'
with p.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['id','year','authors','paper_title','doi','topic','evidence_grade','verification_scope','transfer_limit'])
    w.writerows(rows)
print('papers',len(rows),'registered',p)
