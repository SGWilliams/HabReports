"""
CreateHabReport.py
This script creates PDF habitat model reports for GAP species.

Created on Tue Jun 06 13:54:40 2017
@authors: Linda Schueck and Steve Williams

=======================================================================
Public Functions:
 get_config_values(configFile) --reads data from configuration file
     configFile -- config file name (currently hard coded to be modelReport.cfg
     config file should be a text file with the following information.  
       Note that non of the strings are in quotes.

     [SETUP]
     home = C:/myCodeDirectory/

     [DB]
     SpeciesConnectionString = DRIVER={SQL Server};
       SERVER=<mySQLServerNAME/INSTANCE>;
       DATABASE=<mySQLServerDatabase>e;Trusted_Connection=True
     WHRdBConnectionString = DRIVER={SQL Server};
       SERVER=<mySQLServerNAME/INSTANCE>;
       DATABASE=<mySQLServerDatabase>;Trusted_Connection=True
     AnalDBConnectionString = DRIVER={SQL Server};
       SERVER=<mySQLServerNAME/INSTANCE>;
       DATABASE=<mySQLServerDatabase>;Trusted_Connection=True

     [PDF]
     wkhtmltopdf = C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe


 processSppReport(spp) -- processes given species
     spp -- 6 character GAP species code
   
=======================================================================
"""
import io
try:
    import ConfigParser  # python 2.7
except:
    import configparser   # python 3.x
    pass
import pandas as pd
import numpy as np
from pandas import DataFrame
import pyodbc
import sys, os
from jinja2 import Environment, FileSystemLoader
import pdfkit
import time

# CONFIGURATION
# =======================================================================
pd.options.display.max_colwidth = 1000
headerhtml_file = ''

configFile="modelReport.cfg"

# SET REPLACE/SKIP OPTION
# =======================================================================
rVar = raw_input("Replace Existing Reports? (Y/n): ")
if rVar == "Y" or rVar == "y" or rVar == "":
    print "Replacing existing reports"
    sVar = "Replace"
else:
    print "Keeping existing reports"
    sVar = "Keep"
print ""

# FUNCTIONS
# =======================================================================
# Get configuration values from local config file
def get_config_values(configFile): 	
    config_values = { 
		 'fileDir':"",
        'Species_con':"",
        'WHRdB_con':"",
		 'AnalDB_con':"",
        'wkhtmltopdf_exe':"",
		}
    try:
        try: 
            config =  ConfigParser.RawConfigParser()  #python 2.7
        except:
            config = configparser.ConfigParser() #python 3.x
            pass
        config.read(configFile)
        #Grab file settings
        config_values['fileDir'] = config.get('SETUP','home')
        config_values['Species_con'] = config.get('DB','SpeciesConnectionString')
        config_values['WHRdB_con'] = config.get('DB','WHRdBConnectionString')
        config_values['AnalDB_con'] = config.get('DB','AnalDBConnectionString')
        config_values['wkhtmltopdf_exe'] = config.get('PDF','wkhtmltopdf')       
    except Exception as e:
		#logging.debug('configuration file error')
		#logging.error(e)
        print(e)
        exit()
    return config_values

# -----------------------------------------------------------------------
# TODO need to add some error handling in case species returns no data in one of the SQL statements
# Generate tables from DBs for inclusion in report, then renders and exports as PDF
def processSppReport(spp):

    mappath = '<img src="file:///'+fileDir+'MAPs/'+spp+'_CONUS_HabMap_2001v1.png" id="habmap"/>'

    #sql = "WITH t AS (SELECT LEFT(RIGHT(tblModelStatus.strSpeciesModelCode, 2), 1) AS seas, RIGHT(RIGHT(tblModelStatus.strSpeciesModelCode, 2), 1) AS region, tblModelStatus.whoEditingComplete, tblModelStatus.whoInternalReviewComplete, tblModelStatus.strUC FROM tblModelStatus INNER JOIN tblAllSpecies ON tblModelStatus.strSpeciesModelCode = tblAllSpecies.strSpeciesModelCode WHERE (RIGHT(RIGHT(tblModelStatus.strSpeciesModelCode, 2), 1) IN ('1', '2', '3', '4', '5', '6')) AND (tblModelStatus.strUC = '"+ spp +"' ) AND (tblAllSpecies.ysnInclude = 1) ), s as (SELECT CASE seas WHEN 'w' THEN 'Winter' WHEN 's' THEN 'Summer' WHEN 'y' THEN 'Year-round' END AS season, tblRegionDef.strRegionName as region, t_1.whoEditingComplete, t_1.whoInternalReviewComplete FROM t AS t_1 INNER JOIN tblRegionDef ON t_1.region = tblRegionDef.intRegionCode) SELECT season + ' ' + region + ':' as Submodel , whoEditingComplete as 'Model Editor(s)',  whoInternalReviewComplete as 'Model Reviewer(s)' from s  ORDER BY Submodel"
    ##print(sql)
    #EditorsTable = pd.read_sql(sql, WHRdB_con)
    ##print("Editor Info: " + EditorsTable)

    sql = "SELECT[strRegionName] + ' ' + [strSeasonName] + ': ' as Submodel,[memHMNotes] as 'Comments' FROM [WHRdB].[dbo].[tblModelingAncillary] WHERE left([strSpeciesModelCode], 6) = '"+ spp +"' and  ysnHandModel = 1 ORDER BY Submodel"
    #print(sql)
    HandModelTable = pd.read_sql(sql, WHRdB_con)
    #print("Hand Model Info: " + HandModelTable)

    sql = "select strCommonName as CommonName, strFullSciName as ScientificName, RTRIM(strModelStatus) as ModelStatus from Species_Database.dbo.tblAllSpecies where strUniqueID = '"+ spp +"'"
    #print(sql)
    speciesList = pd.read_sql(sql, Species_con)
    #print("Species Info: " + speciesList)
    speciesInfo=speciesList.to_json()
    common=speciesList.CommonName[0]
    sciname=speciesList.ScientificName[0]

    sql = "SELECT	strWhoEditorUC AS WhoEditor, strWhoReviewUC AS WhoReview FROM	WHRdB.dbo.tblWhoUC WHERE	strUC = '"+ spp +"'"
    #print(sql)
    whoList = pd.read_sql(sql, WHRdB_con)
    #print("whoList: " + whoList)
    whoEditor=whoList.WhoEditor[0]
    whoReview=whoList.WhoReview[0]

    sql = " SELECT intITIScode as ITIScode, intNSglobal as NSglobal, strDoiHM as DOIpath   FROM GAP_AnalyticDB.dbo.tblTaxa   WHERE strUC = '"+ spp +"'"
    #print(sql)
    IdentifiersList = pd.read_sql(sql, AnalDB_con)
    #print("Species Info: " + speciesList)
    itis = IdentifiersList.ITIScode[0]
    nsid = IdentifiersList.NSglobal[0]
    doipath = IdentifiersList.DOIpath[0]

    sql = "select strSpeciesModelCode as ModelCode, intLSGapMapCode as MapUnitCode, ysnPres as Present, ysnPresAuxiliary as PresentAuxiliary, right(strSpeciesModelCode, 2) as seasonRegion from WHRdB.dbo.tblSppMapUnitPres where strSpeciesModelCode in (select strSpeciesModelCode from WHRdB.dbo.tblAllSpecies where strUC = '"+ spp +"' and ysnInclude = 1) and (ysnPres = 1 or ysnPresAuxiliary = 1) "
    #print(sql)
    presenceList = pd.read_sql(sql, WHRdB_con)
    #print("Presence: " )
    #print(presenceList)

    sql = "With auxVariables as ( SELECT Season = CASE tblAllSpecies.strSeasonCode WHEN 'S' THEN 'Summer' WHEN 'W' THEN 'Winter' WHEN 'Y' THEN 'Year Round' END, Region = CASE tblAllSpecies.intRegionCode WHEN 1 THEN 'NW' WHEN 2 THEN 'UM' WHEN 3 THEN 'NE' WHEN 4 THEN 'SW' WHEN 5 THEN 'GP' WHEN 6 THEN 'SE' END, CONVERT(nvarchar, strAvoid) as 'Human Impact Avoidance', CASE WHEN intElevMin = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intElevMin) END as 'Minimum elevation', CASE WHEN intElevMax = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intElevMax) END as 'Maximum elevation', CASE WHEN ysnHydroFW = 1 THEN CONVERT(nvarchar, 'Yes') ELSE CONVERT(nvarchar,'') END as 'Utilizes Flowing Water', CASE WHEN intIntoBuffFW = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intIntoBuffFW) END as 'Into flowing', CASE WHEN intFromBuffFW = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intFromBuffFW) END as 'From flowing', CASE WHEN ysnHydroOW = 1 THEN CONVERT(nvarchar, 'Yes') ELSE CONVERT(nvarchar,'') END as 'Utilizes Open/Standing Water', CASE WHEN intIntoBuffOW = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intIntoBuffOW) END as 'Into open/standing', CASE WHEN intFromBuffOW = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intFromBuffOW) END as 'From open/standing', CASE WHEN ysnHydroWV = 1 THEN CONVERT(nvarchar, 'Yes') ELSE CONVERT(nvarchar,'') END as 'Utilizes Wet Vegetation', CASE WHEN intIntoBuffWV = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intIntoBuffWV) END as 'Into wet', CASE WHEN intFromBuffWV = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intFromBuffWV) END as 'From wet', CASE strSalinity WHEN 'Brackish/Saltwater Only' THEN CONVERT(nvarchar,'Brackish') WHEN 'Freshwater Only' THEN CONVERT(nvarchar,'Freshwater') WHEN 'Marine Only' THEN CONVERT(nvarchar,'Marine') ELSE strSalinity END as 'Salinity', CONVERT(nvarchar,strStreamVel) as 'Velocity', CASE WHEN cbxContPatch = 1 THEN CONVERT(nvarchar,'Yes') ELSE CONVERT(nvarchar,'') END as 'Contiguous patch', CASE WHEN intContPatchSize = 9999 THEN CONVERT(nvarchar,'NR') ELSE CONVERT(nvarchar, intContPatchSize) END as 'Minimum size', strEdgeType as 'Edge type usage', CONVERT(nvarchar,intEdgeEcoWidth) as 'Ecotone width', CASE strUseForInt WHEN 'Utilizes Forest Interior' THEN CONVERT(nvarchar,'Uses') WHEN 'Avoids Forest Interior' THEN CONVERT(nvarchar,'Avoids') ELSE null END as 'Forest interior usage', CONVERT(nvarchar,strForIntBuffer) as 'Distance from edge', CONVERT(nvarchar,intAuxBuff) as 'Distance from PMU', CASE WHEN ysnHandModel = 1 THEN CONVERT(nvarchar, 'Yes') ELSE CONVERT(nvarchar,'') END as 'Hand Modeled' FROM WHRdB.dbo.tblAllSpecies INNER JOIN WHRdB.dbo.tblModelingAncillary ON tblAllSpecies.strSpeciesModelCode = tblModelingAncillary.strSpeciesModelCode WHERE (ysnInclude = 1 AND WHRdB.dbo.tblAllSpecies.strUC = '"+ spp +"') ), up as ( SELECT Region, Season, colName, VariableValue FROM (SELECT * FROM auxVariables) aux CROSS APPLY (Values ('Human Impact Avoidance',[Human Impact Avoidance]), ('Minimum elevation',[Minimum elevation]), ('Maximum elevation',[Maximum elevation]), ('Utilizes Flowing Water',[Utilizes Flowing Water]), ('Into flowing',[Into flowing]), ('From flowing',[From flowing]), ('Utilizes Open/Standing Water',[Utilizes Open/Standing Water]), ('Into open/standing',[Into open/standing]), ('From open/standing',[From open/standing]), ('Utilizes Wet Vegetation',[Utilizes Wet Vegetation]), ('Into wet',[Into wet]), ('From wet',[From wet]), ('Salinity',[Salinity]), ('Velocity',[Velocity]), ('Contiguous patch',[Contiguous patch]), ('Minimum size',[Minimum size]), ('Edge type usage',[Edge type usage]), ('Ecotone width',[Ecotone width]), ('Forest interior usage',[Forest interior usage]), ('Distance from edge',[Distance from edge]), ('Distance from PMU',[Distance from PMU]), ('Hand Modeled',[Hand Modeled])) x(colName, VariableValue)) SELECT roworder = CASE colName WHEN 'Contiguous patch' THEN 3 WHEN 'Minimum size' THEN 4 WHEN 'Edge type usage' THEN 6 WHEN 'Ecotone width' THEN 7 WHEN 'Forest interior usage' THEN 9 WHEN 'Distance from edge' THEN 10 WHEN 'Distance from PMU' THEN 13 WHEN 'Utilizes Flowing Water' THEN 16 WHEN 'Into flowing' THEN 17 WHEN 'From flowing' THEN 18 WHEN 'Utilizes Open/Standing Water' THEN 20 WHEN 'Into open/standing' THEN 21 WHEN 'From open/standing' THEN 22 WHEN 'Utilizes Wet Vegetation' THEN 24 WHEN 'Into wet' THEN 25 WHEN 'From wet' THEN 26 WHEN 'Salinity' THEN 28 WHEN 'Velocity' THEN 30 WHEN 'Human Impact Avoidance' THEN 32 WHEN 'Minimum elevation' THEN 34 WHEN 'Maximum elevation' THEN 35 WHEN 'Hand Modeled' THEN 37 END, Region AS 'Region*', Season, CASE colName WHEN 'Hand Modeled' THEN 'Hand Modeled' WHEN 'Human Impact Avoidance' THEN 'Human Impact Avoidance' WHEN 'Minimum elevation' THEN 'Elevation Limit - Minimum (m)' WHEN 'Maximum elevation' THEN 'Elevation Limit - Maximum (m)' WHEN 'Utilizes Flowing Water' THEN 'Flowing Water' WHEN 'Into flowing' THEN 'Distance Into (m)' WHEN 'From flowing' THEN 'Distance From (m)' WHEN 'Utilizes Open/Standing Water' THEN 'Open/Standing Water' WHEN 'Into open/standing' THEN 'Distance Into (m)' WHEN 'From open/standing' THEN 'Distance From (m)' WHEN 'Utilizes Wet Vegetation' THEN 'Wet Vegetation' WHEN 'Into wet' THEN 'Distance Into (m)' WHEN 'From wet' THEN 'Distance From (m)' WHEN 'Salinity' THEN 'Water Salinity' WHEN 'Velocity' THEN 'Water Velocity' WHEN 'Contiguous patch' THEN 'Contiguous Patch' WHEN 'Minimum size' THEN 'Minimum Size (ha)' WHEN 'Edge type usage' THEN 'Edge Type Usage' WHEN 'Ecotone width' THEN 'Ecotone Width (m)' WHEN 'Forest interior usage' THEN 'Forest Interior Usage' WHEN 'Distance from edge' THEN 'Distance From Edge (m)' WHEN 'Distance from PMU' THEN 'Distance From Primary Map Units (m)' END as Variable, VariableValue FROM up"
    #print(sql)
    variableTable  = pd.read_sql(sql, WHRdB_con)
    #print("Modelling Variables: " )
    #print( variableTable)
    var_pivot = pd.pivot_table(variableTable, index=['roworder','Variable'], columns=['Season', 'Region*'], values = 'VariableValue', aggfunc=np.sum)
    #print(var_pivot)

    sql = "SELECT   Season = CASE tblAllSpecies.strSeasonCode		 WHEN 'S' THEN 'Summer'		 WHEN 'W' THEN 'Winter'		 WHEN 'Y' THEN 'Year Round'		 END,    'Region*' = CASE tblAllSpecies.intRegionCode		 WHEN 1 THEN 'NW'		 WHEN 2 THEN 'UM'		 WHEN 3 THEN 'NE'		 WHEN 4 THEN 'SW'		 WHEN 5 THEN 'GP'		 WHEN 6 THEN 'SE'		 END,   (CAST(tblSppMapUnitPres.intLSGapMapCode AS nvarchar) + ' - ' + tblMapUnitDesc.strLSGapName) as ModellingMapUnit,   tblSppMapUnitPres.ysnPres + tblSppMapUnitPres.ysnPresAuxiliary * 2 AS intMU   FROM    tblAllSpecies    INNER JOIN tblSppMapUnitPres ON   tblAllSpecies.strSpeciesModelCode = tblSppMapUnitPres.strSpeciesModelCode   INNER JOIN tblMapUnitDesc ON   tblSppMapUnitPres.intLSGapMapCode = tblMapUnitDesc.intLSGapMapCode WHERE    (ysnInclude = 1 AND WHRdB.dbo.tblAllSpecies.strUC = '"+ spp +"' )"
    #print(sql)
    MapUnitTable  = pd.read_sql(sql, WHRdB_con)
    #print("Mapping Units: " )
    #print( MapUnitTable)
    mu_pivot = pd.pivot_table(MapUnitTable, index=['ModellingMapUnit'], columns=['Season', 'Region*'], values = 'intMU', aggfunc=np.sum)
    #print(mu_pivot)

    sql = "SELECT distinct CAST(dbo.tblCitations.memCitation as nvarchar(max)) FROM (dbo.tblAllSpecies INNER JOIN dbo.tblSppCitations  ON dbo.tblAllSpecies.strSpeciesModelCode = dbo.tblSppCitations.strSpeciesModelCode)  INNER JOIN dbo.tblCitations ON  dbo.tblSppCitations.strRefCode = dbo.tblCitations.strRefCode  WHERE dbo.tblAllSpecies.strUC = '"+ spp +"' ORDER BY CAST(dbo.tblCitations.memCitation as nvarchar(max))"
    #print(sql)
    citationsList = pd.read_sql(sql, WHRdB_con)
    #print("Citations: " )
    #print( citationsList )

    # MAY NEED TO DO SOMETHING ABOUT BAD CHARACTERS IN CITATIONS
    #Citatiosvalue = unicode(citationsList, "utf-8", errors="ignore")
    #print(citationsList)

    print('Done Loading Tables for spp=' +spp)
    header_template_vars =  {
                     "title" : "Habitat Model Report Header for "+ spp ,
                     "common_name": common,
                     "sci_name": sciname,
                     "spp": spp,
                     "itis": itis,
                     "DOIpath": doipath,
                     "pdf_css": pdf_css,
                     "usgs_logo": usgs_logo,
                     }
    headerhtml_out = header_template.render(header_template_vars)
    headerhtml_file = io.open('tmp_Header.html',"w")
    headerhtml_file.write(headerhtml_out)
    headerhtml_file.close()
    pdfkit_options['header-html'] = 'file:///' + fileDir + 'tmp_Header.html'
    pdfkit_options['footer-html'] = 'file:///' + fileDir + 'HabReportTemplateFooter.html'

    template_vars = {                     
                     "title" : "Habitat Model Report Header for "+ spp ,
                     "common_name": common,
                     "sci_name": sciname,
                     "spp": spp,
                     "itis": itis,
                     "nsid": nsid,
                     "whoEditor": whoEditor,
                     "whoReview": whoReview,
                     "DOIpath": doipath,
                     "pdf_css": pdf_css,
                     "modelling_variables_pvtable": var_pivot.to_html(classes='ModelVariables', na_rep=''),
                     "modelling_mapunits_pvtable": mu_pivot.to_html(classes='MapUnits', na_rep=''),
                     "citations_table": citationsList.to_html(classes='Citations', na_rep=''),
                     "map_file": mappath,
                     "pdf_css": pdf_css,
                     "usgs_logo": usgs_logo,
                     "todaysdate" : time.strftime("%B %d, %Y"),        #("%d/%m/%Y"),
                     #"editors" : EditorsTable.to_html(classes='Editors', na_rep=''),
                     "handmodel_table" : HandModelTable.to_html(classes='HandModel', na_rep='')
                    }
    html_out = template.render(template_vars)
    html_file = io.open('tmp_SppRpt.html',"w")
    html_file.write(html_out)
    html_file.close()
    fn = fileDir + "PDFs/" + spp + '_CONUS_2001v1_SppRpt.pdf'
    pdf = pdfkit.from_string(html_out, str(fn), configuration=pdfconfig, options=pdfkit_options)

# CONFIGURATION
# =======================================================================
config = []
config = get_config_values(configFile)

pdfconfig = pdfkit.configuration(wkhtmltopdf=config['wkhtmltopdf_exe'])
fileDir = config['fileDir']
Species_con = pyodbc.connect(config['Species_con'])
WHRdB_con = pyodbc.connect(config['WHRdB_con'])
AnalDB_con = pyodbc.connect(config['AnalDB_con'])

#usgs_logo = '<img src="file:///'+fileDir+'html_files/USGS_ID_green.png" id="usgslogo"/>'
usgs_logo = 'file:///'+fileDir+'html_files/USGS_ID_white.png'

env = Environment(loader=FileSystemLoader('.'))
template = env.get_template("HabReportTemplate.html")
header_template = env.get_template("HabReportTemplateHeader.html")

pdf_css = '<link rel="stylesheet" type="text/css" href="file:///' + fileDir + 'html_files/stylesheet.css">'
pdfkit_options = {
    'page-size': 'Letter',
    'orientation': 'Landscape',
    'margin-top': '.8in',
    'margin-right': '0.4in',
    'margin-bottom': '0.5in',
    'margin-left': '0.4in',
    'encoding': "UTF-8",
    'no-outline': None,
}

# SET UP LOOP ON SPECIES TO RUN REPORTS
# =======================================================================
## List of species that you want to generate Habitat Report PDFs for.
sppListFile = fileDir + 'HabReport NOT RUN.txt'

# Iterate through each spp in sppList.
sppList = open(sppListFile,"r")
for aline in sppList:
    values = aline.split()
    strTif = values[0]
    strUC = strTif[:6]
    fnPDF = fileDir + "PDFs/" + strUC + '_CONUS_2001v1_SppRpt.pdf'

    # Implement replace/skip 
    if (sVar == 'Keep' and str(os.path.isfile(fnPDF)) == 'True'):
        print strUC + " output exists - skipping..."
    else:
        print "Working on " + strUC + "..."
        processSppReport(strUC)

# CLOSE DB CONNECTIONS
# =======================================================================
# TODO need to make sure the connections get closedSpecies_con.close()
WHRdB_con.close()
AnalDB_con.close()

