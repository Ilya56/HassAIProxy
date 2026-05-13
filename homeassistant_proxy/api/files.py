from fastapi import APIRouter

from homeassistant_proxy.dependencies import Authenticated, FileServiceDep
from homeassistant_proxy.models.api_models import FileContent, FileInfo, FileListResponse, FileSearchResponse

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/list", response_model=FileListResponse, operation_id="listAllowedFiles")
async def list_allowed_files(
    _: Authenticated,
    file_service: FileServiceDep,
    path_prefix: str | None = None,
) -> FileListResponse:
    return FileListResponse(files=await file_service.list_files(path_prefix=path_prefix))


@router.get("/read", response_model=FileContent, operation_id="readAllowedFile")
async def read_allowed_file(_: Authenticated, file_service: FileServiceDep, path: str) -> FileContent:
    return await file_service.read_file(path)


@router.get("/search", response_model=FileSearchResponse, operation_id="searchAllowedFiles")
async def search_allowed_files(
    _: Authenticated,
    file_service: FileServiceDep,
    query: str,
    path: str | None = None,
    path_prefix: str | None = None,
) -> FileSearchResponse:
    return FileSearchResponse(
        matches=await file_service.search_files(query=query, path=path, path_prefix=path_prefix)
    )


@router.get("/metadata", response_model=FileInfo, operation_id="getFileMetadata")
async def get_file_metadata(_: Authenticated, file_service: FileServiceDep, path: str) -> FileInfo:
    return await file_service.get_metadata(path)
