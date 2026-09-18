from __future__ import annotations


XML_FIXTURE = """<selection>
  <writings>
    <writing id="1" level="6" unit="1">
      <learner id="l1" nationality="xx" />
      <topic id="t1" />
      <grade>80</grade>
      <text>I <change><selection>go</selection><tag><symbol>AGV</symbol><correct>goes</correct></tag></change> now.</text>
    </writing>
    <writing id="2" level="7" unit="2">
      <learner id="l2" nationality="yy" />
      <topic id="t2" />
      <grade>70</grade>
      <text>This block has <change><selection></selection><tag><symbol>MP</symbol><correct>to</correct></tag></change> fallback.</text>
    </writing>
  </writings>
</selection>
"""


MALFORMED_WRITING_BLOCK = """    <writing id="3" level="8" unit="3">
      <learner id="l3" nationality="zz" />
      <topic id="t3" />
      <grade>60</grade>
      <text>I <change><selection>am</selection><tag><symbol>VT</symbol><correct>was</correct></tag></change> malformed <broken></text>
    </writing>
"""


CSV_FIXTURE = """,writingID,level,unit,learnerID,nationality,topicID,topic,grade,text,lvno,prof,original,corrected,POS
1,1,6,1,l1,xx,t1,masked,80,"<change><selection>go</selection><tag><symbol>AGV</symbol><correct>goes</correct></tag></change>",1,1,masked,masked,masked
"""

